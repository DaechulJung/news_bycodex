# 에이전트/AI 일일 트렌드 하네스 설계

## 목적

이 저장소는 HTML 파일 형태의 일일 에이전트/AI 트렌드 인텔리전스 보고서를 생성하는 코덱스(Codex) 네이티브 하네스를 구현합니다. 이 시스템은 단순한 뉴스 수집기가 아닙니다. 소스 중심의 여러 리포터들이 신호를 수집하고, 분석가들이 신호를 구조화하며, 편집자가 간결한 일일 브리핑을 생성하는 작은 뉴스룸처럼 동작해야 합니다.

첫 번째 마일스톤은 실제 웹 수집을 수행하고 하나의 보고서를 작성하는 로컬 MVP(최소 기능 제품)입니다:

```text
reports/YYYY-MM-DD.html
```

## 범위

MVP에는 실제 소스 수집, 원시 스냅샷 저장, 정규화, 중복 제거, 트렌드 스코어링, 에이전트 지원 합성 및 HTML 보고서 렌더링이 포함됩니다. 저장소 로컬 프롬프트, 스킬, 메모리 및 데이터 파일을 사용하여 코덱스 감독 하에 로컬에서 실행됩니다.

MVP에는 자동화된 스케줄링, 호스팅된 대시보드, 인증이 많이 필요한 X(트위터) 수집, 다중 사용자 워크플로우 또는 장기 데이터베이스 인프라가 포함되지 않습니다. 이러한 기능들은 로컬 하네스가 편집 워크플로우를 입증한 후의 이후 단계에 해당합니다.

## 아키텍처 방향

하네스는 저장소 로컬 코덱스 하네스로 시작하여 나중에 안정적인 부분들을 플러그인 또는 MCP 서버로 발전시킬 것입니다.

1. 우선 저장소 로컬 하네스: 검사하고 반복하기가 가장 쉽습니다.
2. 두 번째로 코덱스 플러그인: 안정적인 스킬, 프롬프트 및 명령을 패키징합니다.
3. 세 번째로 MCP 도구: 워크플로우가 안정되면 반복적인 수집, 검색, 저장 또는 렌더링 작업을 지속 가능한 도구로 이동시킵니다.

코덱스는 조정 에이전트 역할을 합니다. 저장소는 운영 규칙, 재사용 가능한 스킬, 소스 구성, 메모리 파일, 프롬프트, 원시 데이터, 처리된 데이터 및 보고서를 제공합니다.

## 저장소 구조

```text
AGENTS.md
memory/
  interests.md
  noise_patterns.md
  trend_history.md
prompts/roles/
  editor_in_chief.md
  community_reporter.md
  research_reporter.md
  product_reporter.md
  developer_reporter.md
  trend_analyst.md
  html_publisher.md
skills/
  collect-rss/
  collect-web/
  collect-search/
  normalize-items/
  analyze-trends/
  render-html-report/
configs/
  sources.yaml
  keywords.yaml
data/
  raw/YYYY-MM-DD/
  processed/YYYY-MM-DD/
reports/
  YYYY-MM-DD.html
```

## 에이전트 역할

`Editor-in-Chief (편집장)`은 실행을 조정하고, 소스 카테고리를 할당하며, 커버리지 공백을 확인하고, 최종 HTML 보고서를 승인합니다.

`Community Reporter (커뮤니티 리포터)`는 GeekNews, Hacker News, Reddit 커뮤니티 및 유사한 토론 소스에서 빠르게 움직이는 커뮤니티 신호를 수집합니다.

`Research Reporter (리서치 리포터)`는 arXiv, Papers with Code, 벤치마크 및 연구 프로젝트 신호를 수집합니다.

`Product Reporter (제품 리포터)`는 OpenAI, Google, Anthropic, Hugging Face, Product Hunt 및 공식 블로그의 제품 및 회사 발표를 추적합니다.

`Developer Reporter (개발자 리포터)`는 GitHub 트렌딩, 릴리스, 저장소, 개발자 도구 및 프레임워크 채택 신호를 추적합니다.

`Trend Analyst (트렌드 분석가)`는 중복을 제거하고, 클러스터링하며, 분류하고, 점수를 매기며, 각 트렌드가 왜 중요한지 설명합니다.

`HTML Publisher (HTML 퍼블리셔)`는 최종 브리핑을 읽기 쉬운 독립형 HTML 파일로 렌더링합니다.

## 소스 전략

수집은 다음과 같은 순서로 신뢰할 수 있고 마찰이 적은 메커니즘을 선호해야 합니다:

1. 지원하는 소스에 대한 RSS 또는 공개 API.
2. RSS/API 커버리지가 약한 공개 페이지에 대한 HTML 크롤링.
3. 키워드 기반 트렌드 감지를 위한 검색 기반 발견.
4. 인증이 많이 필요한 소스는 격리된 스킬이 존재한 후에만 사용.

초기 소스 그룹:

- 커뮤니티: GeekNews, Hacker News, Reddit `r/MachineLearning`.
- 리서치: arXiv, Papers with Code.
- 회사/제품: OpenAI, Google, Anthropic, Hugging Face, Product Hunt.
- 개발자: GitHub 트렌딩 및 관련 저장소 릴리스.
- 검색: `LLM Agent`, `agentic framework`, `deep agent`, `autonomous coding agent`, `AI agent framework`, `LLM Model` 등과 같은 키워드.

X(트위터)는 계정 접근, API 정책 및 속도 제한으로 인해 공개 RSS나 HTML 소스와는 운영적으로 다르기 때문에 MVP에서는 선택 사항으로 취급됩니다.

## 데이터 흐름

각 실행은 다음 파이프라인을 따릅니다:

```text
소스 수집 (source collection)
-> 원시 스냅샷 저장 (raw snapshot storage)
-> 정규화된 항목 레코드 (normalized item records)
-> 중복 제거 (deduplication)
-> 주제 클러스터링 (topic clustering)
-> 트렌드 스코어링 (trend scoring)
-> 편집 합성 (editorial synthesis)
-> HTML 발행 (HTML publishing)
```

원시 소스 출력은 `data/raw/YYYY-MM-DD/` 아래에 저장됩니다. 처리된 레코드는 `data/processed/YYYY-MM-DD/` 아래에 저장됩니다. 보고서는 `reports/` 아래에 저장됩니다.

## 정규화된 트렌드 항목

수집된 모든 항목은 다음과 같은 형태로 변환되어야 합니다:

```json
{
  "title": "string",
  "url": "string",
  "source": "string",
  "published_at": "ISO-8601 string or null",
  "summary": "string",
  "category": "model | agent_framework | coding_agent | research | product | tooling | benchmark | company | other",
  "maturity": "rumor | prototype | beta | released | adopted",
  "impact": "low | medium | high | strategic",
  "signal_strength": 1,
  "why_it_matters": "string",
  "related_items": []
}
```

## 트렌드 스코어링

첫 번째 스코어링 모델은 복잡하기보다는 설명 가능해야 합니다. 다음 항목으로 각 항목에 점수를 매깁니다:

- 소스 신뢰성 (source credibility)
- 최신성 (recency)
- `memory/trend_history.md` 대비 참신성 (novelty)
- 교차 소스 확인 (cross-source confirmation)
- 개발자 트랙션 (developer traction)
- 제품 또는 연구의 중요성 (product or research significance)
- 에이전트/AI 트렌드와의 관련성 (relevance to Agent/AI trends)

보고서는 강한 신호와 약한 신호를 분리해야 합니다. 약한 신호는 중요해질 가능성이 있을 때 가치가 있지만, 명확하게 표시되어야 합니다.

## 메모리

메모리 파일은 하네스를 편집적으로 일관되게 유지합니다:

- `memory/interests.md`: 우선순위 주제, 제품, 모델 제품군, 에이전트 프레임워크 및 회사 이름.
- `memory/noise_patterns.md`: 반복되는 가치가 낮은 패턴, 스팸성 키워드, 중복된 발표 스타일 및 주의해서 다뤄야 할 소스.
- `memory/trend_history.md`: 참신성 검사 및 후속 감지를 지원하기 위해 이전에 다룬 주요 트렌드.

메모리 업데이트는 명시적이고 검토 가능해야 합니다. 하네스는 편집 메모리를 조용히 다시 작성해서는 안 됩니다.

## 스킬

스킬은 코덱스의 재사용 가능한 운영 단위입니다. MVP는 다음에 대한 스킬을 정의해야 합니다:

- RSS/API 수집.
- HTML 수집.
- 검색 수집.
- 정규화.
- 트렌드 분석.
- HTML 보고서 렌더링.

각 스킬에는 명확한 입력, 출력, 오류 동작 및 예제가 포함되어야 합니다. 소스별 세부 정보는 프롬프트 내에 하드코딩되는 것이 아니라 실용적인 구성(config) 파일에 속해야 합니다.

## HTML 보고서

MVP 보고서는 CSS가 포함된 독립형 HTML 파일이어야 합니다. 다음이 포함되어야 합니다:

- 경영진 요약 (executive summary)
- 주요 트렌드 (top trends)
- 모델 및 제품 업데이트 (model and product updates)
- 에이전트 프레임워크 및 코딩-에이전트 업데이트 (agent framework and coding-agent updates)
- 연구 및 벤치마크 업데이트 (research and benchmark updates)
- 개발자 생태계 신호 (developer ecosystem signals)
- 주시해야 할 약한 신호 (weak signals to watch)
- 노이즈 또는 연기된 항목 (noise or deferred items)
- 소스 커버리지 및 수집 실패 (source coverage and collection failures)

시각적 스타일은 스캔하기 쉬워야 합니다: 명확한 제목, 간결한 카드 또는 섹션, 소스 링크, 성숙도 및 영향력에 대한 레이블, 그리고 짧은 편집 요약.

## 실패 처리

실패한 소스가 전체 실행을 실패하게 해서는 안 됩니다. 수집 오류는 다음에 기록됩니다:

```text
data/raw/YYYY-MM-DD/errors.jsonl
```

독자가 커버리지의 한계를 이해할 수 있도록 보고서에는 누락되거나 실패한 소스 그룹이 공개되어야 합니다.

## 보안 및 소스 준수

비밀정보, 쿠키, 브라우저 프로필 및 유료 검색 자격 증명은 커밋되어서는 안 됩니다. 공식 API 및 RSS 피드를 선호하십시오. 크롤링의 경우 보수적인 속도 제한을 사용하고, 적절할 때 클라이언트를 식별하며, 소스의 제한 사항을 존중하십시오.

## 테스트 및 검증

MVP에는 정규화, 중복 제거, 트렌드 스코어링 및 HTML 렌더링에 대한 픽스처 기반 테스트가 필요합니다. 라이브 소스 테스트는 결정론적 단위 테스트와 분리되어야 합니다. 유효한 실행은 주어진 날짜에 대해 원시 스냅샷, 처리된 트렌드 레코드 및 읽기 쉬운 HTML 보고서를 생성하는 것입니다.

## 구현 단계

1단계: 저장소 구조, 역할 프롬프트, 메모리 파일, 소스 구성 및 보고서 템플릿을 생성합니다.

2단계: RSS/API 및 단순한 공개 HTML 소스에 대한 첫 번째 수집 스킬을 구현합니다.

3단계: 정규화, 중복 제거 및 트렌드 스코어링을 구현합니다.

4단계: HTML 렌더링 및 완전한 로컬 보고서 실행을 구현합니다.

5단계: 어느 부분을 코덱스 플러그인 자산 또는 MCP 도구로 만들지 평가합니다.
