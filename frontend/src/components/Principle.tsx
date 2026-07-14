/**
 * E3 — "왜 특별한가": 무환각 원리 설명.
 *
 * 이 페이지의 주장은 코드가 실제로 하는 일과 한 글자도 어긋나면 안 된다. 과장은 이 서비스가
 * 반대하는 바로 그것이다. 그래서 "모든 값이 실측"이라고 쓰지 않는다 — 파고·풍속은 지점에
 * 따라 KHOA 실측이거나 Open-Meteo 예보 백필이다(DATA_SOURCES.md).
 *
 * 실측/예보 구분은 이제 화면에 실제로 표기된다(risk.py 가 관측 출처를 BasisValue.
 * observed_source 로 전달, CitationChip 이 [실측]/[예보] 배지 표시). 아래 "수치마다 표기"
 * 문장은 그 배관이 연결된 뒤에야 되살린 것 — 코드가 안 하는 일을 여기 쓰면 안 된다.
 */
export function PrincipleSection() {
  return (
    <section className="principle">
      <div className="section-heading">
        <h2>AI는 이 화면의 숫자를 하나도 만들지 않습니다</h2>
        <p>
          보통의 AI 안내는 그럴듯한 파고·풍속·시각을 스스로 지어냅니다. 이 서비스는 AI가
          숫자를 지어낼 수 없도록 <b>구조로</b> 막았습니다.
        </p>
      </div>

      <ol className="pipeline" role="list">
        <li className="pipeline-step">
          <span className="pipeline-num" aria-hidden="true">
            1
          </span>
          <div>
            <h3>공공 데이터를 그대로 가져옵니다</h3>
            <p>
              국립해양조사원(KHOA) 관측부이의 실측값과 기상청의 공식 특보를 씁니다. 관측 센서가
              없는 지점은 Open-Meteo 수치예보로 채웁니다. 어느 쪽이든 사람이나 AI가 만들어 낸
              값이 아니라, 공개된 공공 데이터를 그대로 옮긴 값입니다. 어떤 수치가 실측이고
              어떤 수치가 예보인지는 브리핑의 수치마다 [실측]·[예보]로 구분해 표기합니다.
            </p>
          </div>
        </li>

        <li className="pipeline-step">
          <span className="pipeline-num" aria-hidden="true">
            2
          </span>
          <div>
            <h3>위험도와 시간은 코드가 계산합니다</h3>
            <p>
              안전·주의·위험 등급, 근거 수치, '가장 안전한 시간'까지 모두 고정된 규칙을 따르는
              계산 결과입니다. AI에게 묻지 않으므로 같은 데이터에서는 언제나 같은 답이 나옵니다.
            </p>
          </div>
        </li>

        <li className="pipeline-step">
          <span className="pipeline-num" aria-hidden="true">
            3
          </span>
          <div>
            <h3>AI는 숫자 없이 말로 옮기기만 합니다</h3>
            <p>
              AI가 쓴 문장에 숫자가 하나라도 섞이면 그 문장은 폐기하고 코드가 만든 안내로
              바꿉니다. 검사는 문장을 만들 때 한 번, 화면에 내보낼 때 또 한 번 — 두 번 합니다.
            </p>
          </div>
        </li>
      </ol>

      <div className="contrast">
        <div className="contrast-col">
          <h3>AI가 하는 일</h3>
          <ul>
            <li>확정된 등급을 쉬운 말로 풀어 설명</li>
            <li>비전문가가 읽을 문장의 어투와 흐름</li>
          </ul>
        </div>
        <div className="contrast-col">
          <h3>AI가 할 수 없는 일</h3>
          <ul>
            <li>파고·풍속·수온 같은 수치 말하기</li>
            <li>'몇 시가 안전하다'고 시각 말하기</li>
            <li>등급을 바꾸거나 뒤집기</li>
          </ul>
        </div>
      </div>

      <p className="principle-confession">
        <b>모르면 모른다고 말합니다.</b> 관측값이 없으면 비슷한 값으로 메우지 않고 '정보없음'
        으로 표시합니다. 파고나 풍속처럼 위험도를 좌우하는 값이 없으면 '안전'으로 판단하지
        않고 한 단계 보수적으로 봅니다.
      </p>
    </section>
  );
}
