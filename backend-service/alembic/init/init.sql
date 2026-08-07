
-- 8. 게시판 
INSERT INTO tn_board(bbs_ty, sj, cn, rdcnt, use_at, reg_dt, reg_id, mod_dt, mod_id) 
VALUES 
('001', '공지사항#1', '공지사항#1...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#2', '공지사항#2...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#3', '공지사항#3...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#4', '공지사항#4...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#5', '공지사항#5...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#6', '공지사항#6...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#7', '공지사항#7...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#8', '공지사항#8...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#9', '공지사항#9...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#10', '공지사항#10...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#11', '공지사항#11...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#12', '공지사항#12...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#13', '공지사항#13...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#14', '공지사항#14...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#15', '공지사항#15...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#16', '공지사항#16...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#17', '공지사항#17...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#18', '공지사항#18...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#19', '공지사항#19...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#20', '공지사항#20...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#21', '공지사항#21...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#22', '공지사항#22...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#23', '공지사항#23...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#24', '공지사항#24...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#25', '공지사항#25...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#26', '공지사항#26...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#27', '공지사항#27...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#28', '공지사항#28...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#29', '공지사항#29...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#30', '공지사항#30...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#31', '공지사항#31...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#32', '공지사항#32...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#33', '공지사항#33...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#34', '공지사항#34...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#35', '공지사항#35...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#36', '공지사항#36...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#37', '공지사항#37...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#38', '공지사항#38...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#39', '공지사항#39...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin'),
('001', '공지사항#40', '공지사항#40...', 0, 'Y', CURRENT_TIMESTAMP, 'admin', CURRENT_TIMESTAMP, 'admin');

-- 9. 관심종목 (Watchlist — 공개 상장 종목 샘플; 모의 데이터)
INSERT INTO tn_watchlist (workspace_id, ticker, issuer_nm, market, sector, currency, target_price, alert_price, priority, use_at, memo, reg_dt, reg_id, mod_dt, mod_id)
VALUES
(1, '005930', '삼성전자',        'KOSPI',  'IT/반도체',   'KRW',  90000.00,   70000.00,  '1', 'Y', '반도체 업황 반등 모니터링',     CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, '000660', 'SK하이닉스',      'KOSPI',  'IT/반도체',   'KRW', 200000.00,  150000.00,  '1', 'Y', 'HBM 수요 추적',                CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, '035420', 'NAVER',           'KOSPI',  '인터넷',      'KRW', 230000.00,  180000.00,  '2', 'Y', '광고/커머스 매출 점검',         CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, '005380', '현대차',          'KOSPI',  '자동차',      'KRW', 280000.00,  220000.00,  '2', 'Y', '전기차 믹스/배당 확인',         CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, '051910', 'LG화학',          'KOSPI',  '화학/2차전지','KRW', 450000.00,  350000.00,  '3', 'Y', '배터리 사업부 마진 추적',       CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'AAPL',   'Apple Inc.',      'NASDAQ', 'Technology',  'USD',    240.00,     180.00,  '1', 'Y', '서비스 매출 비중 확대 점검',     CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'MSFT',   'Microsoft Corp.', 'NASDAQ', 'Technology',  'USD',    480.00,     380.00,  '1', 'Y', 'Azure 성장률 모니터링',         CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'NVDA',   'NVIDIA Corp.',    'NASDAQ', 'Semiconductors','USD',  160.00,     110.00,  '1', 'Y', 'AI 가속기 가이던스 추적',       CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR');

-- 10. 포트폴리오 (master)
INSERT INTO tn_portfolio (workspace_id, portfolio_id, portfolio_nm, sort_ordr, use_at, description, reg_dt, reg_id, mod_dt, mod_id)
VALUES
(1, 'core',   '코어 성장 포트폴리오', 1, 'Y', '국내외 대형 성장주 코어 비중', CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'income', '배당 인컴 포트폴리오', 2, 'Y', '배당/인컴 중심 방어 포트폴리오', CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'tech',   '글로벌 테크 포트폴리오', 3, 'Y', '미국 빅테크 집중 포트폴리오', CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR');

-- 11. 보유종목 (detail)
INSERT INTO tn_holding (workspace_id, portfolio_id, ticker, holding_nm, quantity, avg_price, use_at, description, reg_dt, reg_id, mod_dt, mod_id)
VALUES
(1, 'core',   '005930', '삼성전자',   120, 72000.00,  'Y', '코어 반도체 비중',       CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'core',   '035420', 'NAVER',       30, 195000.00, 'Y', '인터넷 성장 노출',       CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'income', '005380', '현대차',      40, 235000.00, 'Y', '배당 매력 보유',         CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'income', '051910', 'LG화학',      10, 410000.00, 'Y', '2차전지 인컴 일부',      CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'tech',   'AAPL',   'Apple Inc.',  50, 195.00,    'Y', '미국 빅테크 코어',       CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR'),
(1, 'tech',   'NVDA',   'NVIDIA Corp.',80, 118.00,    'Y', 'AI 반도체 집중',         CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'MGR');

-- 13. 메시지 큐 (Kafka 대체 DB 큐 — 시세/체결 틱 인제스트 done/failed 이력 샘플; pending 은 consumer 가 소비)
INSERT INTO tn_message_queue (topic, payload, status, retry_count, error, reg_dt, reg_id, mod_dt, mod_id)
VALUES
('nav.snapshot', '{"timestamp": "2026-06-30T09:00:00", "nav": 1000.0, "benchmark": 1000.0, "daily_return": 0.0, "drawdown": 0.0}', 'done',   0, NULL,            CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'system'),
('nav.snapshot', '{"timestamp": "2026-06-30T09:00:10", "nav": 1004.2, "benchmark": 1002.1, "daily_return": 0.42, "drawdown": 0.0}', 'done',   0, NULL,            CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'system'),
('nav.snapshot', '{"timestamp": "2026-06-30T09:00:20", "nav": 999.8, "benchmark": 1001.0, "daily_return": -0.44, "drawdown": -0.42}', 'failed', 1, 'sample failure', CURRENT_TIMESTAMP, 'MGR', CURRENT_TIMESTAMP, 'system');
