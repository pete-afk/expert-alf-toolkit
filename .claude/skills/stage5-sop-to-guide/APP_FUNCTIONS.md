# App Functions (앱태스크 연동) 스펙

Stage 5 Step 5-A에서 태스크 기획 시 참조하는 앱함수 스펙.

## 판단 기준

태스크를 기획할 때, 해당 시나리오가 **앱함수로 처리 가능한지 먼저 판단**한다.

**처리 방식:** 전체 태스크 초안 작성 완료 후, 모든 태스크를 **일괄 분류**한다 (태스크별 개별 판단 금지 — 배치 처리로 LLM 호출 최소화).

판단 기준:
- 태스크가 조회/실행하려는 대상이 `app_functions_services`에 포함된 서비스 데이터인가?
- 아래 서비스별 스펙 표에서 해당 함수가 존재하는가?

---

## 서비스별 앱함수 스펙

### 이지어드민 (`app_functions_services`에 `"이지어드민"` 포함 시)

| 함수명 | 처리 가능 시나리오 |
|--------|------------------|
| `getOrders` / `getOrder` | 주문 조회, 주문 상태 확인 |
| `cancelOrder` | 주문 취소 |
| `changeAddress` | 배송지 변경 |
| `setReturn` | 반품 접수 |
| `setExchange` | 교환 접수 |
| `trackDelivery` | 배송 추적 |
| `addRefundInfo` | 환불 정보 등록 |
| `verifyAccountHolder` | 예금주 확인 (환불 계좌 검증) |
| `restoreOrder` / `copyOrder` | 주문 복원/복사 |
| `getOrderTags` / `setOrderTag` / `deleteOrderTag` | 주문 태그 관리 |
| `getShopId` | 쇼핑몰 ID 조회 (내부 분기용) |

### 사방넷 (`app_functions_services`에 `"사방넷"` 포함 시)

| 함수명 | 처리 가능 시나리오 |
|--------|------------------|
| `getOrders` / `getOrder` | 주문 조회 |
| `cancelOrder` | 주문 취소 |
| `returnOrder` | 반품 접수 |
| `exchangeOrder` | 교환 접수 |
| `changeShippingAddress` | 배송지 변경 |
| `restoreCanceledOrder` | 취소 복원 |
| `getShopId` | 쇼핑몰 ID 조회 |

### 카페24 (`app_functions_services`에 `"카페24"` 포함 시) — Task 함수 기준

| 함수명 | 처리 가능 시나리오 |
|--------|------------------|
| `getOrders` | 주문 조회 |
| `requestCancelOrder` / `completeCancelOrder` | 주문 취소 (2단계) |
| `returnOrder` | 반품 신청 |
| `requestExchangeOrder` | 교환 신청 |
| `getExchangeableProducts` | 교환 가능 상품 확인 |
| `getCoupons` / `getCustomerCoupons` | 쿠폰 조회 |
| `issueCoupon` | 쿠폰 발급 |

> General 함수 중 `sendMobileOTP` / `verifyMobileOTP` / `checkIfReturnable` / `checkIfExchangeable` 등 검증·확인용 함수는 Task 함수와 함께 앱함수 단독으로 처리 가능.

### 스프레드시트 (항상 사용 가능, 서비스와 무관)

| 함수명 | 활용 예시 |
|--------|----------|
| `get_row_by_key` / `get_rows_by_index` | 설정 값 조회, FAQ 불러오기 |
| `append_row` | 상담 로그 기록, 신청 내역 저장 |
| `update_row_by_key` | 상태 업데이트 |
| `delete_row_by_key` | 항목 삭제 |

---

## 태스크 처리 방식 분류

분류 결과를 각 태스크 파일 상단 요약표에 다음 열로 추가:

| 처리 방식 | 의미 |
|-----------|------|
| `앱함수` | 앱태스크 연동으로 처리 가능 — 코드노드 불필요 |
| `코드노드` | 커스텀 코드노드 개발 필요 |
| `앱함수 + 코드노드` | 앱함수로 일부 처리, 추가 로직은 코드노드 필요 |

`app_functions=false`인 경우: 모든 태스크를 코드노드 기준으로 기획하고, 처리 방식 열을 생략한다.
