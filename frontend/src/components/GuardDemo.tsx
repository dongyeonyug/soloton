import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { checkProse, fetchGuardDemo } from "../api/client";
import type { GuardDemo, GuardVerdict } from "../types";

const MAX_TEXT_LEN = 300;

/**
 * E1 — '거짓말 차단'을 눈으로 보여주는 페이지.
 *
 * 문장(입력)은 재현한 예시지만, 판정(위반 표시·폐기·대체)은 서버의 실제 가드가
 * 지금 실행한 결과다. 프론트는 어떤 판단도 하지 않고 결과만 그린다.
 */
export function GuardDemoPage() {
  const [demo, setDemo] = useState<GuardDemo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGuardDemo()
      .then(setDemo)
      .catch((e) => {
        console.error(e);
        setError("시연 데이터를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="verify">
      <div className="section-heading">
        <h2>정말 막히는지, 지금 확인해 보세요</h2>
        <p>
          AI가 지어냈을 법한 문장을 이 사이트가 실제로 쓰는 검사 코드에 그대로 통과시켜
          봤습니다.
        </p>
      </div>

      <p className="verify-honesty">
        아래 문장들은 실제 AI가 남긴 기록이 아니라 <b>흔한 환각 유형을 재현한 예시</b>입니다.
        다만 판정은 이 사이트가 실제로 쓰는 검사 코드가 방금 실행한 결과입니다 — 미리 적어둔
        답이 아닙니다.
      </p>

      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
        </div>
      )}

      <div aria-live="polite">
        {loading && <p className="muted verify-context">불러오는 중…</p>}
        {demo && (
          <>
            <p className="muted verify-context">
              {demo.spot_name}의 현재 관측·등급 위에서 실행했습니다.
            </p>
            {/* Safari/VoiceOver 는 list-style:none 이면 목록 의미를 지운다 → role 명시 */}
            <ol className="verify-cases" role="list">
              {demo.cases.map((c) => (
                <li key={c.id} className="verify-case">
                  <div className="verify-case-head">
                    <h3>{c.title}</h3>
                    <p>{c.note}</p>
                  </div>
                  <VerdictView verdict={c} />
                </li>
              ))}
            </ol>
          </>
        )}
      </div>

      <TryItYourself />
    </main>
  );
}

/** 가드 판정 한 건: AI 초안 → 검사 → 실제 서빙 문장. */
function VerdictView({ verdict }: { verdict: GuardVerdict }) {
  return (
    <div className="verdict">
      <div className="verdict-step">
        <span className="verdict-step-label">AI 초안</span>
        <p className="verdict-draft">
          <MarkedProse text={verdict.text} spans={verdict.violation_spans} />
        </p>
      </div>

      <div className={`verdict-result ${verdict.blocked ? "blocked" : "passed"}`}>
        {verdict.blocked ? (
          <>
            <span className="verdict-icon" aria-hidden="true">
              ✕
            </span>
            <span>
              폐기 — 지어낸 수치·시각 {verdict.violations.length}건:{" "}
              <span className="verdict-tokens">{verdict.violations.join(" · ")}</span>
            </span>
          </>
        ) : (
          <>
            <span className="verdict-icon" aria-hidden="true">
              ✓
            </span>
            <span>통과 — 지어낸 수치·시각 없음</span>
          </>
        )}
      </div>

      <div className="verdict-step">
        <span className="verdict-step-label">이 초안이라면 서빙되는 문장</span>
        <p className="verdict-served">
          {verdict.served_prose}
          <span className={`prose-badge ${verdict.llm_used ? "ai" : "tpl"}`}>
            {verdict.llm_used ? "AI 문장" : "기본 안내"}
          </span>
        </p>
      </div>
    </div>
  );
}

/**
 * 위반 구간에 표시를 입힌 원문.
 *
 * 서버 스팬은 코드포인트 오프셋이므로 Array.from 으로 코드포인트 배열을 만들어 자른다
 * (JS 문자열 인덱스는 UTF-16 단위라 이모지가 섞이면 어긋난다).
 */
function MarkedProse({ text, spans }: { text: string; spans: [number, number][] }) {
  if (spans.length === 0) return <>{text}</>;

  const chars = Array.from(text);
  const parts: ReactNode[] = [];
  let cursor = 0;

  spans.forEach(([start, end]) => {
    if (start > cursor) parts.push(chars.slice(cursor, start).join(""));
    parts.push(
      <mark key={`${start}-${end}`} className="violation">
        {chars.slice(start, end).join("")}
      </mark>,
    );
    cursor = end;
  });
  if (cursor < chars.length) parts.push(chars.slice(cursor).join(""));

  return <>{parts}</>;
}

/** 원클릭 예시 — 첫 경험을 성공 경로로 유도(자유 입력은 그대로 열어 둠). */
const EXAMPLES: { text: string; hint: string }[] = [
  { text: "지금 파도는 2미터가 넘으니 위험합니다", hint: "수치 날조" },
  { text: "오후 세 시쯤이 가장 안전합니다", hint: "시각 날조" },
  { text: "바람이 잦아들어 오후로 갈수록 나아집니다", hint: "숫자 없는 문장" },
];

/** 심사위원이 직접 문장을 써서 가드를 시험해 보는 입력창. */
function TryItYourself() {
  const [text, setText] = useState("");
  const [verdict, setVerdict] = useState<GuardVerdict | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    setChecking(true);
    setError(null);
    setVerdict(null); // 새 검사 중에 이전 판정이 남아 있으면 '라이브 판정'이라는 주장이 흐려진다
    checkProse(trimmed)
      .then(setVerdict)
      .catch((err) => {
        console.error(err);
        setVerdict(null);
        setError("검사에 실패했어요. 잠시 후 다시 시도해 주세요.");
      })
      .finally(() => setChecking(false));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    check(text);
  };

  const tryExample = (t: string) => {
    setText(t);
    check(t);
  };

  return (
    <section className="tryit">
      <div className="section-heading">
        <h2>직접 시험해 보세요</h2>
        <p>AI가 할 법한 문장을 써서 검사해 보세요. 같은 코드가 판정합니다.</p>
      </div>

      <form className="tryit-form" onSubmit={submit}>
        <label htmlFor="tryit-input">검사할 문장</label>
        <div className="tryit-row">
          <input
            id="tryit-input"
            type="text"
            value={text}
            maxLength={MAX_TEXT_LEN}
            placeholder="예: 오늘 파도는 1미터로 잔잔합니다"
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" disabled={!text.trim() || checking}>
            {checking ? "검사 중…" : "검사"}
          </button>
        </div>
        <div className="tryit-examples" role="group" aria-label="예시 문장으로 검사">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.text}
              type="button"
              className="tryit-example"
              disabled={checking}
              onClick={() => tryExample(ex.text)}
            >
              “{ex.text}” <span className="tryit-example-hint">{ex.hint}</span>
            </button>
          ))}
        </div>
      </form>

      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
        </div>
      )}

      <div aria-live="polite">{verdict && <VerdictView verdict={verdict} />}</div>
    </section>
  );
}
