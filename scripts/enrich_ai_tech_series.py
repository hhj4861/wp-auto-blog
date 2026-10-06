"""One-time editorial composition from the existing public articles.

The checked-in HTML, rather than this network-based helper, is the reviewed
publication input. All new examples are editorial illustrations, not test claims.
"""
from html import escape
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
STYLE = '''<style>
.wpab-article{line-height:1.85;color:#243247;overflow-wrap:anywhere}
.wpab-article h2{margin:2.5em 0 .8em;line-height:1.4}.wpab-article h3{margin-top:1.8em}
.wpab-article table{display:block;overflow-x:auto;border-collapse:collapse;width:100%;margin:24px 0;font-size:.95em}
.wpab-article th,.wpab-article td{padding:12px;border:1px solid #dbe3ed;vertical-align:top;min-width:110px}
.wpab-article th{background:#edf2f8}.wpab-article blockquote{margin:24px 0;padding:18px 22px;background:#f4f7fb;border-left:4px solid #347080}
.wpab-article #quick-answer{padding:22px;background:#edf5f4;border-radius:16px}
.wpab-article .tp-diagram{margin:30px 0;padding:24px;background:#f3f6fa;border:1px solid #dce4ef;border-radius:18px}
.wpab-article .tp-diagram figcaption{font-weight:700;color:#123949;line-height:1.5;margin-bottom:18px}
.wpab-article .tp-flow{display:flex;align-items:stretch;gap:9px;flex-wrap:wrap}
.wpab-article .tp-node{flex:1 1 130px;min-width:0;background:#fff;border:1px solid #c7d8e1;border-radius:12px;padding:14px;box-sizing:border-box}
.wpab-article .tp-node strong{display:block;color:#12576a;font-size:1.05em}.wpab-article .tp-node span{display:block;font-size:.88em;margin-top:7px;line-height:1.6}
.wpab-article .tp-arrow{align-self:center;color:#426579;font-size:24px;font-weight:700}
.wpab-article .tp-split{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-top:14px}
.wpab-article .tp-stop{border-top:4px solid #a45236}.wpab-article .tp-pass{border-top:4px solid #238471}
.wpab-article .tp-note{font-size:.88em;line-height:1.65;margin:16px 0 0;color:#4b5e70}
.wpab-article pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:20px;background:#152b3b;color:#ecf4fa;border-radius:12px;font-size:.88em}
.wpab-article .tp-bar{height:18px;background:#2f7c83;border-radius:4px;margin:5px 0 12px}
@media(max-width:600px){.wpab-article .tp-diagram{padding:16px}.wpab-article .tp-flow{flex-direction:column}.wpab-article .tp-node{flex:auto;width:100%}.wpab-article .tp-arrow{transform:rotate(90deg)}.wpab-article .tp-split{grid-template-columns:1fr}}
</style>'''

def flow(key, title, nodes, note):
    boxes = '<div class="tp-arrow" aria-hidden="true">→</div>'.join('<div class="tp-node"><strong>'+escape(a)+'</strong><span>'+escape(b)+'</span></div>' for a,b in nodes)
    return f'<figure class="tp-diagram" id="{key}"><figcaption>{escape(title)}</figcaption><div class="tp-flow">{boxes}</div><p class="tp-note">{escape(note)}</p></figure>'

def branch(key, title, top, left, right, note):
    def box(x,cls=''):
        return '<div class="tp-node '+cls+'"><strong>'+escape(x[0])+'</strong><span>'+escape(x[1])+'</span></div>'
    return '<figure class="tp-diagram" id="'+key+'"><figcaption>'+escape(title)+'</figcaption>'+box(top)+'<div style="text-align:center;font-size:24px;color:#426579" aria-hidden="true">↓</div><div class="tp-split">'+box(left,'tp-pass')+box(right,'tp-stop')+'</div><p class="tp-note">'+escape(note)+'</p></figure>'

MUSE = '''
<h2>작동 흐름으로 이해하기: 요청 한 문장이 결과가 되기까지</h2>
<p>에이전트를 평가할 때는 “답변을 잘했나”와 “맡긴 일이 끝났나”를 나누어 보아야 합니다. 여행 일정을 표로 만들었다고 항공권이 예약된 것은 아니고, 홍보 문구를 작성했다고 매장 계정에 게시된 것도 아닙니다. 사용자가 정한 목표가 자료 수집, 판단, 초안, 승인, 실행 중 어디까지인지 먼저 정해야 결과를 정확히 평가할 수 있습니다.</p>
{flow}
<p>이 도식은 공식 제품 화면을 복제한 것이 아니라 업무를 위임하는 과정을 설명한 편집부의 개념도입니다. Muse의 모든 작업이 정해진 다섯 단계로 실행된다는 뜻도 아닙니다. 중요한 점은 중간 산출물을 눈으로 확인할 수 있게 만드는 것입니다. 자료를 못 읽었는데 그럴듯한 답변부터 만들면, 마지막 단계에서 문장만 다듬어서는 문제를 해결할 수 없습니다.</p>
<h3>완료 조건에는 동사와 확인할 증거를 함께 적자</h3>
<p>“고객 문의를 처리해줘”는 너무 넓습니다. 분류만 할지, 답변을 작성할지, 발송까지 할지에 따라 필요한 권한과 실수의 영향이 달라집니다. 첫 과제는 “문의 목록에서 반복 질문을 묶어 검토용 표를 만들고, 각 행에 원문 위치를 남겨줘” 정도가 적당합니다. 표에 없는 질문을 억지로 다섯 개 채우지 말고, 자료가 부족한 항목은 부족하다고 표시하도록 요청하세요.</p>
<h2>실전 설계: 작은 쇼핑몰의 주간 문의 정리</h2>
<p>다음은 실제 Muse 실행 결과가 아닌 <strong>편집부가 만든 가상 업무 예시</strong>입니다. 운영자가 지난주 문의 목록과 현재 배송·교환 안내문을 준비했다고 가정하겠습니다. 시작부터 고객 계정 전체를 연결하기보다 개인정보를 뺀 작은 자료로 분류와 답변의 품질을 먼저 확인할 수 있습니다.</p>
<blockquote>지난주 월요일 00:00부터 일요일 23:59까지, 한국 시간 기준으로 접수된 문의를 정리해줘. 내가 제공한 문의 목록과 최신 운영 안내문만 근거로 써줘. 배송·교환·상품 정보·기타로 묶고, 질문 원문 위치와 답변 근거를 함께 표시해줘. 안내문에 없는 약속은 만들지 말고 ‘담당자 확인 필요’로 남겨줘. 결과는 검토용 표와 반복 질문 답변 초안으로 작성하고, 고객 발송이나 공개 게시 전에는 승인을 요청해줘.</blockquote>
<p>이 요청은 자료 범위, 기간, 결과 형식, 모르는 내용의 처리, 실행 권한을 함께 정합니다. 실제 연결 도구에서 이 범위를 설정할 수 있는지는 계정에서 확인해야 합니다. 프롬프트에 제한을 써두는 것과 서비스 자체의 접근 권한을 좁히는 것은 별개이므로, 연결 설정도 함께 살펴보세요.</p>
<table><thead><tr><th>가상 문의</th><th>검토용 결과의 예</th><th>사람이 확인할 부분</th></tr></thead><tbody><tr><td>“오늘 주문하면 내일 오나요?”</td><td>배송 문의. 출고 마감 시간과 일반 배송 안내를 연결. 내일 도착 확약은 보류.</td><td>재고·지역·휴일 정보가 있는가?</td></tr><tr><td>“개봉했는데 교환되나요?”</td><td>교환 문의. 해당 상품의 교환 조건 원문을 제시하고 적용 여부 확인 요청.</td><td>단순 변심인지 불량인지 구별했는가?</td></tr><tr><td>“이 상품과 지난번 제품의 차이는?”</td><td>상품 정보 문의. 두 제품의 확인 가능한 사양만 나란히 정리.</td><td>다른 모델의 사양이 섞이지 않았는가?</td></tr></tbody></table>
<p>좋은 결과물에는 매끄러운 답변뿐 아니라 <strong>어떤 자료로 답했는지, 어디부터 확인이 필요한지</strong>가 남습니다. 위 사례에서 “내일 도착합니다”처럼 고객이 좋아할 문장을 만드는 것은 쉬워도, 자료에 없는 도착일을 확약하면 운영 부담이 커집니다. 에이전트에 맡길 가치는 이런 확인 과정을 줄이면서도 근거를 남기는 데 있습니다.</p>
<h2>승인 경계: 읽을 수 있다는 것이 보낼 수 있다는 뜻은 아니다</h2>
{branch}
<p>Meta의 <a href="https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse">보안 설계 설명</a>에 나오는 권한 통제는 이런 경계를 이해하는 데 도움이 됩니다. 다만 실제 승인 대상은 작업·연결 서비스·이전에 허용한 범위에 따라 달라질 수 있습니다. 위 도식은 처음 운영할 때 권하는 보수적인 업무 구분이며, 제품의 모든 승인 규칙을 그대로 옮긴 표는 아닙니다.</p>
<h3>승인하기 전에 볼 네 가지</h3>
<ul><li><strong>대상:</strong> 어느 계정, 어느 고객, 어느 게시물인가?</li><li><strong>내용:</strong> 미리 본 초안과 실제 실행할 내용이 같은가?</li><li><strong>범위:</strong> 한 번만 허용하는가, 반복 작업에도 적용하는가?</li><li><strong>결과:</strong> 실행 뒤 확인할 공개 URL·발송 기록·변경 내역은 무엇인가?</li></ul>
<p>예를 들어 할인 안내를 승인할 때 문구만 확인하면 가격이나 적용 기간이 어긋날 수 있습니다. 게시 채널, 시작·종료 시각, 대상 상품, 확인 가능한 가격표를 한 묶음으로 검토하는 편이 좋습니다. 승인 뒤에는 완료 메시지와 실제 게시물을 비교해야 합니다. 이는 Muse만의 문제가 아니라 외부 서비스에 쓰기 작업을 하는 모든 자동화에 필요한 확인입니다.</p>
<h2>작업이 멈췄을 때: 재시도보다 먼저 확인할 것</h2>
<table><thead><tr><th>증상</th><th>먼저 확인</th><th>권하는 대처</th></tr></thead><tbody><tr><td>관련 자료를 못 찾음</td><td>자료 존재 여부, 연결 계정, 조회 기간</td><td>입력 자료를 좁혀 다시 제공하고 누락 목록을 받기</td></tr><tr><td>초안은 있는데 작업이 끝나지 않음</td><td>승인 대기인지, 실행 도구 오류인지</td><td>대기 사유를 확인하고 필요한 단계만 이어가기</td></tr><tr><td>게시 요청 후 성공 여부가 모호함</td><td>대상 서비스에 이미 생성된 결과가 있는지</td><td>실제 게시물을 확인한 뒤 중복 없이 복구하기</td></tr><tr><td>답변 내용이 자꾸 틀림</td><td>최신 운영 규정과 예외 조건 제공 여부</td><td>틀린 사례를 정리해 입력과 완료 기준부터 보완하기</td></tr></tbody></table>
<p>한 번의 실패에 권한을 전부 열어주는 방식은 원인을 가리기 쉽습니다. 자료 부족이면 자료를, 승인 대기면 승인 범위를, 실행 오류면 해당 도구와 결과를 확인해야 합니다. 중복 발송이나 중복 게시 가능성이 있는 작업은 특히 “한 번 더 실행”하기 전에 실제 대상 서비스의 상태부터 확인하는 편이 안전합니다.</p>
<h3>첫 일주일의 도입 판단표</h3>
<p>평가할 때는 초안 수보다 확인 비용을 기록해 보세요. 예를 들어 기존에 문의 정리에 40분이 들고, 에이전트 초안 검토에 15분·수정에 10분이 든다면 총 25분입니다. 이 숫자는 설명을 위한 가정이며 Muse의 측정 성능이 아닙니다. 검토 시간을 빼고 “작성은 2분”만 비교하면 절감 효과를 과장하기 쉽습니다.</p>
<p>일주일 동안 원문 근거가 빠진 항목 수, 사람이 고친 핵심 오류 수, 중복 작업 여부를 함께 기록하세요. 같은 종류의 오류가 반복되면 더 큰 일을 맡기기보다 그 입력 조건을 먼저 고치는 편이 낫습니다. 반대로 짧고 반복적인 일에서 확인 부담이 줄었다면 그다음 연결 자료나 작업 범위를 하나씩 넓혀볼 수 있습니다.</p>
'''
DOTS = '''
<h2>도식으로 보는 클라우드 작업과 내 컴퓨터의 경계</h2>
<p>Dots를 이해할 때 먼저 나눌 것은 <strong>작업이 실행되는 곳과 자료가 있는 곳</strong>입니다. 클라우드에서 동작하는 에이전트라고 해서 꺼진 개인 컴퓨터의 모든 파일을 읽을 수 있는 것은 아닙니다. 반대로 클라우드에서 접근 가능한 자료만으로 끝나는 과제라면 개인 컴퓨터의 로컬 작업과는 다른 조건으로 생각할 수 있습니다.</p>
{branch}
<p>도식은 연결 구조를 설명한 개념도입니다. 실제로 특정 작업이 기기를 꺼도 끝나는지 판단하려면 입력 파일, 실행 프로그램, 결과 저장 위치를 각각 확인해야 합니다. “매주 보고서를 작성하라”는 요청에 노트북 안의 파일이 필요하다면 그 의존성을 없애거나, 승인된 연결 환경에서 접근 가능한 자료로 바꾸어야 합니다. 클라우드 제품이라는 이유만으로 모든 작업의 상시 실행을 보장할 수는 없습니다.</p>
<h2>실전 설계: 매주 읽을 만한 업계 변화 보고서 만들기</h2>
<p>다음은 <strong>직접 실행한 제품 평가가 아닌 편집부의 업무 설계 예시</strong>입니다. 작은 팀이 매주 공식 발표를 확인해 서비스 기획에 참고한다고 가정하겠습니다. 검색 결과를 많이 모으는 것보다 “지난 보고서 이후 실제로 무엇이 바뀌었는가”에 답하는 것이 목표입니다.</p>
<blockquote>매주 월요일 오전 9시, 한국 시간 기준으로 직전 월요일 00:00부터 일요일 23:59까지의 변화를 정리해줘. 내가 지정한 회사의 공식 발표·제품 도움말을 우선해줘. 발표일과 실제 적용일을 구분하고, 이전 보고서와 같은 내용이면 새 소식처럼 넣지 말아줘. 중요한 변화는 최대 5개로 정리하되 부족하면 개수를 채우지 마. 각 항목에 원문, 확인일, 우리 업무에 미치는 영향, 추가 확인 사항을 써줘. 접근 실패한 출처는 별도 목록에 남기고, 결과는 검토용 문서로만 작성해줘.</blockquote>
<p>이 예시는 제품의 숨겨진 명령어가 아닙니다. 어떤 에이전트에게 일을 맡기더라도 필요한 명세입니다. 날짜가 없으면 오래된 발표가 섞이고, “최대 5개” 대신 “반드시 5개”라고 하면 가치가 낮은 항목으로 분량을 채우기 쉽습니다. 출처가 비어 있을 때도 문서가 만들어질 수 있으므로, 자료 확보 여부와 작성 완료 여부를 분리해야 합니다.</p>
<table><thead><tr><th>보고서 칸</th><th>좋은 결과의 조건</th><th>피해야 할 결과</th></tr></thead><tbody><tr><td>무엇이 바뀌었나</td><td>이전 조건과 새 조건을 구체적으로 비교</td><td>“혁신적인 기능 출시” 같은 평가만 적음</td></tr><tr><td>누가 쓸 수 있나</td><td>요금제·지역·관리자 설정을 구분</td><td>일부 계정의 기능을 모두 제공한다고 단정</td></tr><tr><td>언제 적용되나</td><td>발표일과 순차 배포·정식 적용일을 구분</td><td>발표 즉시 누구나 쓸 수 있다고 표현</td></tr><tr><td>왜 우리에게 중요한가</td><td>실제 업무 하나와 연결해 영향 설명</td><td>근거 없이 생산성·매출 향상을 수치로 약속</td></tr><tr><td>무엇이 불확실한가</td><td>접근 실패·미공개 조건·검증 안 된 부분 표시</td><td>정보 없음과 변화 없음을 같은 뜻으로 처리</td></tr></tbody></table>
<p>예를 들어 어떤 서비스가 새 연결 기능을 발표했다면 “연결 기능이 생겼다”는 한 문장보다 우리 요금제에서 쓸 수 있는지, 읽기만 가능한지 쓰기도 가능한지, 관리자 설정이 필요한지를 확인하는 편이 유용합니다. 문서에서 확인되지 않는 조건은 추정으로 채우지 않고 담당자가 직접 볼 질문으로 남기면 됩니다.</p>
<h2>완료·승인 대기·실패를 나누는 작업 흐름</h2>
{flow}
<p>여기서 “재개”는 같은 작업을 무조건 처음부터 반복한다는 뜻이 아닙니다. 조사까지 끝났다면 조사 결과를 보존하고, 권한 때문에 저장을 못 했으면 저장 단계부터 확인합니다. 이미 외부에 게시했을 가능성이 있다면 해당 서비스의 실제 결과를 먼저 조회해야 합니다. 이처럼 상태를 구분하는 운영 설계는 Dots가 자동으로 모든 경우를 해결한다는 보장이 아니라, 사용자가 결과를 확인할 때의 기준입니다.</p>
<h3>검색 결과가 없을 때 보고서에 남길 문장</h3>
<p>“이번 주 변화가 없습니다”와 “공식 사이트 두 곳에 접근하지 못해 변화를 확인하지 못했습니다”는 전혀 다른 결과입니다. 첫 문장은 조사 범위 안에서 확인을 마쳤다는 의미이고, 두 번째는 조사 자체가 불완전하다는 의미입니다. 업무를 맡길 때 이 둘을 분리해 달라고 요청하면 그럴듯하지만 근거가 빈 보고서를 알아차리기 쉽습니다.</p>
<p>마찬가지로 “파일을 만들었습니다”는 결과물의 존재를 말할 뿐 내용의 정확성을 증명하지 않습니다. 실제 파일 링크가 열리는지, 중요한 항목마다 근거가 있는지, 이전 주 내용이 중복되지 않았는지를 확인해야 합니다. 점검 기준을 처음 요청에 넣으면 다음 회차에도 일관되게 비교할 수 있습니다.</p>
<h2>기존 예약 자동화와 Dots 중 무엇을 선택할까?</h2>
<table><thead><tr><th>업무 성격</th><th>편집부의 선택 기준</th><th>예시</th></tr></thead><tbody><tr><td>조건과 출력이 항상 같음</td><td>규칙 기반 자동화부터 검토</td><td>정해진 필드를 다른 표로 복사</td></tr><tr><td>자료의 의미를 읽고 비교해야 함</td><td>에이전트 활용을 소규모 검증</td><td>새 발표와 기존 기능의 차이 설명</td></tr><tr><td>해석과 정확한 실행이 함께 필요</td><td>에이전트의 초안·판단과 검증된 실행 절차를 조합</td><td>업데이트 요약을 검토 후 지정 채널에 게시</td></tr></tbody></table>
<p>이 표는 Dots의 성능 우열을 측정한 결과가 아닙니다. 반복 일정이 있다는 이유만으로 모든 일을 에이전트로 바꿀 필요는 없습니다. 자료 해석이 없는 단순 이동은 규칙이 명확한 방식으로 유지하고, 사람이 읽고 요약하느라 오래 걸리는 부분부터 에이전트를 적용하면 실패 원인도 좁히기 쉽습니다.</p>
<h3>도입 효과는 “생성 시간 + 검토 시간 + 복구 시간”으로 계산</h3>
<p>가령 보고서를 직접 만드는 데 60분이 들었고, 에이전트가 만든 뒤 확인에 20분·오류 수정에 15분이 들었다면 사람의 부담은 35분입니다. 이 수치는 계산 방법을 설명하는 가정으로 Dots의 실제 측정값이 아닙니다. 오류가 난 주의 복구 시간도 합쳐야 장기적인 가치를 판단할 수 있습니다.</p>
<p>평가표에는 원문이 없는 주장 수, 중복 항목 수, 누락된 중요한 변화, 결과물을 실제 업무에 쓴 여부를 기록해 보세요. 보고서가 길어졌다는 사실보다 읽은 사람이 의사결정을 할 수 있었는지가 더 중요합니다. 처음부터 다수의 업무를 연결하면 어느 조건이 품질에 영향을 주었는지 찾기 어려워집니다.</p>
<h2>권한과 기록을 점검하는 세 가지 질문</h2>
<p><strong>첫째, 지금 연결한 계정으로 무엇을 읽을 수 있나?</strong> 허용된 자료 범위를 확인하고, 시험에 필요 없는 자료는 연결하지 않는 편이 좋습니다. 보고서 하나를 위해 조직 전체 자료가 필요한 것은 아닙니다.</p>
<p><strong>둘째, 어떤 행동까지 맡겼나?</strong> 공개 자료 조사, 내부 문서 초안 작성, 외부 발송은 영향이 다릅니다. <a href="https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs">공식 개인정보·안전 FAQ</a>의 proactive research와 실제 실행 권한 구분을 바탕으로 작업 범위를 확인하세요. “알아서 해줘” 대신 저장 위치와 승인 지점을 적는 것이 도움이 됩니다.</p>
<p><strong>셋째, 중단하거나 연결을 끊으면 무엇이 남나?</strong> 앞으로의 접근을 멈추는 일과 이미 만들어진 문서·대화 맥락을 정리하는 일은 다릅니다. 도입 전에 결과 저장 위치, 작업 중단 방법, 자료 정리 책임자를 정해두면 시험이 끝난 뒤에도 불필요한 데이터가 남는 문제를 줄일 수 있습니다.</p>
'''
JEV = '''
<h2>도식으로 이해하기: Jev가 맡는 판단과 프로그램이 맡는 실행</h2>
<p>판단 모델을 넣는다고 자동화의 책임이 모두 모델로 넘어가는 것은 아닙니다. 입력 자료를 준비하고 질문을 설계하는 일, 나온 결과를 어떤 행동으로 연결할지 정하는 일은 별도로 남습니다. 이 경계를 분명하게 만들면 틀린 답변뿐 아니라 통신 오류, 자료 누락, 사람이 확인해야 할 상황도 서로 다르게 처리할 수 있습니다.</p>
{flow}
<p>이 도식은 공식 시스템 화면이 아닌 편집부의 설계 예시입니다. Jev는 문의를 어떤 부서로 보낼지 판단하는 데 쓰고, 실제 티켓 이동은 별도 프로그램이 수행하는 구조입니다. 환불처럼 별도의 권한과 확인이 필요한 행동을 분류 결과 하나만으로 실행하도록 연결하지 않는 것이 좋습니다.</p>
<h2>실전 예시: 고객 문의 한 건을 세 가지 질문으로 나누기</h2>
<p>다음 문장을 가상의 고객 문의로 사용해 보겠습니다. “같은 주문이 두 번 결제된 것 같아요. 로그인은 되지만 주문 번호를 찾지 못했습니다.” 이는 <strong>설명을 위해 만든 입력이며 실제 Jev 호출 결과가 아닙니다.</strong> 이 한 문장에 “잘 처리해줘”라고 요청하는 대신 담당 부서, 긴급도, 추가 정보 필요성을 나누어 정의할 수 있습니다.</p>
<table><thead><tr><th>질문</th><th>유형·기준의 예</th><th>결과를 사용할 곳</th></tr></thead><tbody><tr><td>어느 부서의 확인이 필요한가?</td><td>Choice: 결제 / 기술 / 영업 / 기타·판단 보류</td><td>검토 대기열 선택</td></tr><tr><td>처리 우선순위는 어느 수준인가?</td><td>Score: 일반 문의 / 업무 일부 차질 / 즉시 확인할 중대한 문제</td><td>같은 대기열 안에서 확인 순서 조정</td></tr><tr><td>주문 식별 정보가 충분한가?</td><td>Noul: 입력에 주문을 식별할 정보가 있는지</td><td>추가 정보 요청 여부 검토</td></tr></tbody></table>
<p>위 예시에서는 사람이 읽으면 결제 담당자의 확인이 필요하다고 예상할 수 있지만, 그것을 실제 모델 응답처럼 표시하지는 않습니다. 실제 평가에서는 모델이 반환한 값과 사람이 정한 정답을 따로 기록해야 합니다. 문의에 “로그인”이라는 단어가 있다는 이유로 기술 문의로 보내는 오류가 발생하는지도 확인할 수 있습니다.</p>
<h3>좋은 기준에는 경계 사례와 보류 선택지가 있다</h3>
<p>“긴급도를 1부터 5로 평가해줘”만으로는 점수의 의미가 모호합니다. 매출 영향인지, 이용 불가 시간인지, 개인정보 노출 가능성인지 먼저 정해야 합니다. 처음에는 서로 겹치지 않는 적은 수의 수준으로 시작하고, 각 수준에 해당하는 예시와 해당하지 않는 예시를 함께 정리하는 편이 좋습니다.</p>
<p>선택지에 정답이 없으면 가장 비슷한 틀린 답을 고를 수 있습니다. 문의 분류라면 “기타” 또는 “판단 보류” 경로를 설계하고 그 결과를 사람이 확인하도록 연결하세요. 다만 보류 선택지를 넣는다고 오판이 사라지지는 않습니다. 명확한 문의까지 과도하게 보류하는지도 실제 데이터로 살펴봐야 합니다.</p>
<p>또한 같은 호출의 질문들이 서로의 답을 순서대로 참고한다고 가정하면 안 됩니다. <a href="https://docs.typesafe.ai/introduction">공식 소개 문서</a>는 질문들이 같은 입력 상태에서 독립적으로 처리된다고 설명합니다. “먼저 고른 부서에 따라 다음 질문을 바꾸기”가 필요하다면 코드를 통해 결과를 조합하거나 다음 호출을 별도로 구성해야 합니다.</p>
<h2>숫자로 풀어보기: 선택 확률 0.6인데 confidence는 왜 0.4일까?</h2>
<p>아래는 Choice의 계산 방법을 보여주는 <strong>가상의 분포</strong>입니다. 실제 서비스 성능을 나타내는 숫자가 아닙니다. 선택지가 셋이고 모델이 부여한 확률이 결제 0.6, 기술 0.3, 영업 0.1이라고 해보겠습니다.</p>
<figure class="tp-diagram" id="jev-probability"><figcaption>도식 2 · 확률 분포와 confidence를 구분하기</figcaption><div aria-label="가상의 확률 분포: 결제 60%, 기술 30%, 영업 10%"><strong>결제 0.6</strong><div class="tp-bar" style="width:60%"></div><strong>기술 0.3</strong><div class="tp-bar" style="width:30%;background:#6c8da8"></div><strong>영업 0.1</strong><div class="tp-bar" style="width:10%;background:#93a4b1"></div></div><div class="tp-node"><strong>선택: 결제 / confidence: 0.4</strong><span>(0.6 − 1/3) ÷ (1 − 1/3) = 0.4</span></div><p class="tp-note">가장 높은 확률에서 균등 분포 기준을 빼고 정규화한 값입니다. 실제 정답률 40% 또는 60%를 측정한 결과가 아닙니다.</p></figure>
<p><a href="https://docs.typesafe.ai/confidence">공식 confidence 문서</a>에서 Choice는 선택지 수를 n, 가장 큰 확률을 p라고 할 때 (p − 1/n) ÷ (1 − 1/n)으로 계산합니다. Score는 점수 사이의 순서를 고려하므로 같은 식을 적용하지 않습니다. Noul에는 별도의 confidence 항목이 없습니다. 따라서 서로 다른 유형의 숫자를 이름만 비슷하다고 한 기준으로 섞어 쓰면 안 됩니다.</p>
<p>이 예시에서 확인해야 할 질문은 “0.4면 무조건 실패인가?”가 아닙니다. 우리 문의 데이터에서 어떤 분포일 때 잘못 분류하는지, 잘못 분류했을 때의 손실이 얼마나 큰지입니다. 담당 부서를 바꾸는 정도의 되돌릴 수 있는 처리와 고객에게 돈을 보내는 행동은 같은 임계값으로 판단할 일이 아닙니다.</p>
<h2>불확실한 판단과 API 오류를 같은 실패로 취급하지 말자</h2>
{branch}
<table><thead><tr><th>상황</th><th>의미</th><th>복구 방향</th></tr></thead><tbody><tr><td>정상 응답이지만 판단이 애매함</td><td>자료나 질문만으로 확신하기 어려움</td><td>추가 정보 요청 또는 사람 검토</td></tr><tr><td>필수 응답을 받지 못함</td><td>통신·인증·제한·서비스 오류 가능성</td><td>오류 종류와 재시도 가능 여부부터 확인</td></tr><tr><td>높은 confidence인데 정답과 다름</td><td>확신을 가진 오판</td><td>입력·선택지·평가 데이터와 임계값 재검토</td></tr><tr><td>판단은 맞았지만 실행이 실패함</td><td>후속 시스템에서 문제가 발생</td><td>판단 결과를 보존하고 실행 상태를 확인</td></tr></tbody></table>
<p>예를 들어 응답을 받지 못한 요청을 “낮은 점수”로 저장하면 모델이 실제로 낮게 평가했는지 API가 실패했는지 구분할 수 없습니다. 운영 기록에는 요청 식별자, 사용한 질문 정의의 버전, 성공·실패 유형, 판단값, 실제 실행 결과를 분리해서 남기는 편이 좋습니다. 민감한 문의 원문은 필요한 범위에서만 다루고 접근을 제한해야 합니다.</p>
<h3>후속 처리 의사코드: 판단값을 행동으로 바꾸기</h3>
<pre><code># 설명용 의사코드. 실제 Jev SDK 호출 문법이 아닙니다.
if not response_received:
    record_api_error()
    retry_only_if_appropriate()
elif missing_required_input:
    request_more_information()
elif requires_human_approval or uncertain_for_this_task:
    send_to_review_queue()
else:
    route_ticket_once()
    verify_ticket_destination()</code></pre>
<p>여기에는 고정된 confidence 숫자를 넣지 않았습니다. 자료 없이 특정 기준을 정답처럼 제시할 수 없기 때문입니다. 실제로는 검증 데이터에서 기준을 선택하고, 외부에 영향을 주는 행동에는 별도 승인 조건을 둡니다. 실행 후 응답이 끊겼다면 무작정 다시 이동·발송하기보다 이미 처리됐는지 조회해 중복을 막아야 합니다.</p>
<h2>도입 전 검증: 정확도와 자동 처리 비율을 함께 보자</h2>
<p>처음에는 익명화한 실제 문의를 모아 명확한 사례, 여러 의도가 섞인 사례, 정보가 부족한 사례로 나누어 볼 수 있습니다. 사람이 붙인 정답도 의견이 갈리는지 확인해야 합니다. 질문과 임계값을 고를 때 쓴 데이터와 최종 성능을 확인할 데이터는 분리해야 유리한 예시만 맞춘 결과를 피할 수 있습니다.</p>
<p>가령 검증용 200건 중 120건을 자동 분류하고 그중 114건이 맞았다면, 자동 처리 구간의 정확도는 95%, 전체 중 자동 처리 비율은 60%입니다. <strong>이 숫자는 지표 해석을 위한 가정이며 Jev의 벤치마크가 아닙니다.</strong> 95%만 보고 나머지 80건의 검토 부담을 빼면 실제 운영 비용을 놓칩니다.</p>
<p>반대로 자동 처리 비율만 높이면 잘못된 처리가 늘 수 있습니다. 두 지표와 함께 심각한 오분류 수, 사람 검토 시간, API 오류율, 느린 요청의 지연시간을 기록하세요. 비용도 모델 호출료만 비교하기보다 입력 준비·재시도·검토에 든 비용까지 포함하는 편이 현실적입니다. 판단 모델의 도입 가치는 예쁜 JSON이 아니라 이후 업무가 더 정확하고 관리하기 쉬워졌는지로 평가해야 합니다.</p>
'''

def build():
    additions = {
        'muse': MUSE.replace('{flow}', flow('muse-workflow','도식 1 · 목표에서 확인 가능한 결과까지', [('목표 정의','자료·기간·완료 조건'),('자료 확인','연결 범위 안에서 읽기'),('초안 작성','근거와 미확인 사항'),('승인·실행','허용 범위에서 행동'),('결과 확인','실제 문서·게시물 검토')], '편집부의 업무 위임 개념도. 각 단계의 결과를 확인하고 필요한 지점에서 멈춥니다.')).replace('{branch}', branch('muse-approval','도식 2 · 결과물 작성과 외부 실행을 구분하기',('작업 요청','무엇을 읽고 무엇을 바꿀지 범위를 정합니다.'),('초기 시험 범위','자료 읽기 → 분류 → 검토용 초안. 연결 권한 안에서 수행.'),('추가 확인이 필요한 범위','외부 발송·공개 게시·지출 → 대상과 내용 검토 → 필요한 승인 후 실행.'),'색상뿐 아니라 제목과 설명으로 두 경로를 구분했습니다. 실제 승인 방식은 서비스 설정에 따릅니다.')),
        'dots': DOTS.replace('{branch}',branch('dots-boundary','도식 1 · 같은 요청에도 자료 위치에 따라 달라지는 조건',('사용자가 맡긴 목표','dot의 클라우드 컴퓨터에서 작업을 이어갑니다.'),('클라우드에서 접근 가능한 자료','허용된 웹·연결 서비스 → 조사·검토용 문서 작성. 서비스와 권한 상태 확인 필요.'),('개인 컴퓨터에만 있는 자료','로컬 접근 설정·기기와 연결 상태 확인 필요. 꺼진 기기의 파일까지 접근 가능하다는 뜻은 아닙니다.'),'기본 실행 환경과 로컬 접근은 별개입니다. 실제 작업의 의존성을 확인하는 개념도입니다.')).replace('{flow}',flow('dots-workflow','도식 2 · 주간 보고서의 확인 지점',[('범위 지정','기간·출처·제외 항목'),('조사·비교','이전 보고서와 차이'),('초안 확인','근거·누락·중복 검토'),('완료 또는 보류','확인된 결과만 완료')],'자료 접근 실패 → 누락 명시 후 재조사. 승인 대기 → 승인 후 필요한 단계만 재개. 외부 실행 결과가 모호하면 중복 여부부터 확인합니다.')),
        'jev': JEV.replace('{flow}',flow('jev-workflow','도식 1 · 입력 자료 → 독립적인 판단 → 정책에 따른 실행',[('입력 상태','문의·필수 맥락 정리'),('유형별 질문','부서·우선순위·정보 충족'),('정책 코드','판단값과 승인 조건 조합'),('후속 실행','분류·검토 요청·결과 확인')],'같은 호출의 질문들은 같은 입력에서 독립적으로 판단합니다. 다른 질문의 답이 필요한 처리는 호출 밖에서 조합합니다.')).replace('{branch}',branch('jev-routing','도식 3 · 정상 판단을 받은 뒤에도 경로를 나누기',('응답과 필수 입력을 확인','통신 실패는 별도 오류 경로로 분리한 뒤 판단값을 검토합니다.'),('업무 기준 충족','검증한 정책에 따라 허용된 처리를 수행하고 실제 결과를 확인합니다.'),('불확실하거나 승인 필요','추가 자료 요청 또는 사람 검토. 낮은 확신을 억지로 실행으로 연결하지 않습니다.'),'임계값은 자체 검증으로 결정합니다. 높은 confidence만으로 민감한 행동의 승인을 대체하지 않습니다.')),
    }
    slugs = {'muse':'meta-muse-ai-agent-guide','dots':'openai-dots-ai-agent-guide','jev':'typesafe-jev-decision-model-guide'}
    for name,slug in slugs.items():
        response=requests.get('https://trendpulse.blog/'+slug+'/',timeout=(10,40)); response.raise_for_status()
        soup=BeautifulSoup(response.text,'html.parser'); article=soup.select_one('.wpab-article')
        if not article or article.select_one('.tp-diagram'): raise RuntimeError('Missing original or already enriched: '+name)
        for element in article.select('script, iframe, ins, style, .adsbygoogle'):
            element.decompose()
        # Preserve existing factual sections, insert worked examples before the ending/FAQ.
        headings=article.find_all('h2',recursive=False)
        anchor=next((h for h in headings if '자주 묻는' in h.get_text() or '도입 판단' in h.get_text() or 'AI 에이전트와 함께' in h.get_text()),None)
        if not anchor: raise RuntimeError('Editorial insertion point missing')
        for element in list(BeautifulSoup(additions[name],'html.parser').contents):
            anchor.insert_before(element)
        links=' · '.join('<a href="https://trendpulse.blog/'+s+'/">'+label+'</a>' for n,s,label in [('muse',slugs['muse'],'Meta Muse'),('dots',slugs['dots'],'OpenAI Dots'),('jev',slugs['jev'],'TypeSafe Jev')] if n!=name)
        article.append(BeautifulSoup('<h2>함께 읽으면 좋은 글</h2><p>'+links+'</p>','html.parser'))
        output=STYLE+'\n'+str(article)+'\n'
        (ROOT/'data/editorial/2026-10-06'/f'{name}.html').write_text(output)
        print(name,'visible_chars',len(article.get_text(' ',strip=True)),'diagrams',len(article.select('.tp-diagram')))

if __name__=='__main__':
    build()
