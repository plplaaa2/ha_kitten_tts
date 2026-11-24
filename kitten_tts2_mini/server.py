"""Serve Kitten TTS 2 Mini through Wyoming for Home Assistant Assist.

Related files: config.yaml, Dockerfile, requirements.txt.
"""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import signal
import socket
from urllib.error import URLError
from urllib.request import Request, urlopen

from kittenml import KittenTTS
import numpy as np
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncTcpServer
from wyoming.tts import Synthesize, SynthesizeStart, SynthesizeStop, SynthesizeStopped

MODEL_ID = "KittenML/kitten-tts-2-mini"
PORT = 10500
LANGUAGES = ("ko", "en")
WARMUP_TEXT = {"ko": "안녕하세요.", "en": "Hello."}
LOG = logging.getLogger("kitten_tts2_mini")


class SynthesisService:
    """Load the model once and expose language-specific Wyoming voice IDs."""

    def __init__(self, options):
        self.model = KittenTTS(MODEL_ID, backend="onnx", device="cpu")
        self.speed = float(options.get("speed", 1.0))
        if not 0.5 <= self.speed <= 2.0:
            raise ValueError("speed must be between 0.5 and 2.0")

        self.voices = {
            f"{language}-{name.lower()}": (language, name)
            for language in LANGUAGES
            for name in self.model.available_voices[language]
        }
        language = options.get("language", "ko")
        if language not in LANGUAGES:
            raise ValueError("language must be ko or en")
        default = self.model.available_voices[language][0]
        voice = (options.get("voice") or default).strip().lower()
        self.default_voice = f"{language}-{voice}"
        if self.default_voice not in self.voices:
            raise ValueError(f"Unknown default voice for language {language}")

        attribution = Attribution("KittenML", f"https://huggingface.co/{MODEL_ID}")
        sdk_version = version("kittenml")
        ordered_voices = [self.default_voice]
        ordered_voices.extend(voice_id for voice_id in self.voices if voice_id != self.default_voice)
        self.info = Info(tts=[TtsProgram(
            name="Kitten TTS 2 Mini",
            attribution=attribution,
            installed=True,
            description="Kitten TTS 2 Mini",
            version=sdk_version,
            voices=[
                TtsVoice(
                    name=voice_id,
                    attribution=attribution,
                    installed=True,
                    description=self.voices[voice_id][1],
                    version=sdk_version,
                    languages=[self.voices[voice_id][0]],
                )
                for voice_id in ordered_voices
            ],
        )]).event()

    def synthesize(self, text, voice_id):
        language, voice = self.voices[voice_id]
        samples = np.asarray(
            self.model.generate(text, voice=voice, language=language, speed=self.speed),
            dtype=np.float32,
        ).reshape(-1)
        if not samples.size or not np.isfinite(samples).all():
            raise RuntimeError("Model returned empty or non-finite audio")
        return np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2").tobytes()


class WyomingHandler(AsyncEventHandler):
    """Handle Describe and Synthesize requests on a Wyoming connection."""

    def __init__(self, reader, writer, *, service, executor):
        super().__init__(reader, writer)
        self.service = service
        self.executor = executor
        self.stream_started = False

    async def handle_event(self, event):
        if Describe.is_type(event.type):
            await self.write_event(self.service.info)
            return True
        # Home Assistant also sends a complete Synthesize inside its streaming envelope.
        if SynthesizeStart.is_type(event.type):
            self.stream_started = True
            return True
        if SynthesizeStop.is_type(event.type) and self.stream_started:
            self.stream_started = False
            await self.write_event(SynthesizeStopped().event())
            return True
        if not Synthesize.is_type(event.type):
            return True

        try:
            request = Synthesize.from_event(event)
            text = request.text.strip()
            voice_id = (request.voice and request.voice.name) or self.service.default_voice
            if not isinstance(voice_id, str):
                raise ValueError("Voice must be a string")
        except (AttributeError, KeyError, TypeError, ValueError):
            await self.write_event(Error("Invalid synthesis request", "invalid_request").event())
            return False
        if not text or voice_id not in self.service.voices:
            await self.write_event(Error("Empty text or unknown voice", "invalid_request").event())
            return False

        try:
            loop = asyncio.get_running_loop()
            pcm = await loop.run_in_executor(self.executor, self.service.synthesize, text, voice_id)
        except (Exception, SystemExit) as error:
            LOG.error("Synthesis failed (%s)", type(error).__name__)
            await self.write_event(Error("Speech synthesis failed", "synthesis_failed").event())
            return False

        audio_format = {"rate": self.service.model.sample_rate, "width": 2, "channels": 1}
        await self.write_event(AudioStart(**audio_format).event())
        for offset in range(0, len(pcm), 8192):
            await self.write_event(AudioChunk(audio=pcm[offset:offset + 8192], **audio_format).event())
        await self.write_event(AudioStop().event())
        return True


def publish_discovery(port):
    """Register the listening container with the Supervisor when running as an app."""
    credential = os.getenv("SUPERVISOR_TOKEN")
    if not credential:
        return
    uri = f"tcp://{socket.gethostname()}:{port}"
    body = json.dumps({"service": "wyoming", "config": {"uri": uri}}).encode()
    request = Request(
        "http://supervisor/discovery",
        data=body,
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=5):
            LOG.info("Published Wyoming discovery for %s", uri)
    except (URLError, TimeoutError, OSError):
        LOG.warning("Discovery failed; configure Wyoming manually at %s", uri)


async def run_server(host, options):
    LOG.info("Loading %s (ONNX int8)", MODEL_ID)
    service = SynthesisService(options)
    server = AsyncTcpServer(host, PORT)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    if os.name != "nt":
        loop.add_signal_handler(signal.SIGTERM, stop.set)
    with ThreadPoolExecutor(max_workers=1) as executor:
        default_language, _ = service.voices[service.default_voice]
        for language, text in WARMUP_TEXT.items():
            first_voice = service.model.available_voices[language][0]
            voice_id = service.default_voice if language == default_language else f"{language}-{first_voice.lower()}"
            LOG.info("Preparing %s voices", language)
            await loop.run_in_executor(
                executor, service.synthesize, text, voice_id
            )
        handler = partial(WyomingHandler, service=service, executor=executor)
        await server.start(handler)
        LOG.info("Wyoming listening on %s:%d (default voice: %s)", host, PORT, service.default_voice)
        try:
            await asyncio.to_thread(publish_discovery, PORT)
            await stop.wait()
        finally:
            await server.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--options", type=Path, default=Path("/data/options.json"))
    args = parser.parse_args()
    options = json.loads(args.options.read_text(encoding="utf-8")) if args.options.is_file() else {}
    logging.basicConfig(
        level=logging.DEBUG if options.get("debug_logging") else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_server(args.host, options))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
