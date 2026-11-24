# Kitten TTS 2 Mini for Home Assistant

Kitten TTS 2 Mini를 Home Assistant OS의 Assist에서 음성 합성 엔진으로 사용하는 로컬 앱입니다. CPU에서 ONNX int8 모델을 실행하며 한국어와 영어 음성을 제공합니다.

## 설치

앱 스토어의 저장소 메뉴에 `https://github.com/plplaaa2/ha_kitten_tts#dev`를 추가하면 GitHub의 개발 브랜치에서 앱을 설치할 수 있습니다. 이후 앱을 시작하고 아래 4~5단계에 따라 Wyoming과 Assist를 설정합니다.

로컬 앱으로 설치하려면 다음 단계를 사용합니다.

1. 이 저장소 안의 `kitten_tts2_mini` 폴더를 Samba의 `local_apps` 공유 폴더 또는 Terminal & SSH의 `/local_apps/`에 복사합니다. 최종 경로는 `/local_apps/kitten_tts2_mini/config.yaml`입니다. 이전 버전에서는 로컬 앱 폴더가 `addons` 또는 `/addons/`로 표시될 수 있습니다.
2. Home Assistant의 **설정 → 앱 → 앱 설치**에서 앱 목록을 새로고침한 뒤, **로컬 앱 → Kitten TTS 2 Mini → 설치**를 선택합니다.
3. 앱을 시작한 뒤 로그에 `Wyoming listening`이 표시되는지 확인합니다. 이미지 빌드와 첫 시작 때는 인터넷 연결이 필요합니다. 앱은 시작할 때 한국어와 영어 합성을 준비하며, 모델 캐시는 `/data/huggingface`에 유지됩니다.
4. **설정 → 기기 및 서비스**에서 검색된 **Kitten TTS 2 Mini**를 추가합니다. 자동 검색이 되지 않으면 **통합 구성요소 추가 → Wyoming Protocol**에서 호스트 `local-kitten-tts2-mini`, 포트 `10500`을 입력합니다. 포트는 Supervisor 내부 네트워크에서 사용합니다.
5. **설정 → 음성 어시스턴트**에서 Assist 파이프라인을 편집합니다. **텍스트 음성 변환**에 **Kitten TTS 2 Mini**를 선택하고, 한국어 응답에는 언어 **한국어**와 음성 **Seoyeon**, **Minjun**, **Jihoon** 중 하나를 선택합니다. 음성으로 질문해 합성된 응답을 확인합니다.

## 앱 설정

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `language` | `ko` | Wyoming 요청에 음성이 지정되지 않았을 때 사용할 언어입니다. `ko` 또는 `en`을 선택합니다. |
| `voice` | 빈 문자열 | 선택한 언어의 첫 기본 음성을 사용합니다. 한국어 기본은 `Seoyeon`입니다. 예를 들어 `Minjun`을 입력해 바꿀 수 있습니다. |
| `speed` | `1.0` | 합성 속도입니다. 범위는 `0.5`~`2.0`입니다. |
| `debug_logging` | `false` | 디버그 로그를 활성화합니다. |

옵션을 저장한 뒤 앱을 재시작합니다. Assist에서 음성을 선택하면 해당 음성을 사용합니다.

Assist가 보내는 긴 응답은 문장이 완성되는 대로 합성하여 오디오를 순서대로 전송합니다. 실제 재생 시작 시점은 클라이언트의 버퍼링 방식에 따라 달라집니다.

## 관련 문서

- [Home Assistant 로컬 앱 개발](https://contributors.home-assistant.io/apps/)
- [Wyoming Protocol 통합](https://www.home-assistant.io/integrations/wyoming/)
- [Kitten TTS 2 Mini 모델 카드](https://huggingface.co/KittenML/kitten-tts-2-mini)
