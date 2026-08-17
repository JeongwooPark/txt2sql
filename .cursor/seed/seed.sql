-- llm2sql 개발/데모용 부산 GIS 시드 데이터
--
-- 이 파일은 Cloud Agent 개발 환경에서 앱을 엔드투엔드로 실행하기 위한
-- 자체 완결형(self-contained) 대표 샘플 데이터입니다. 실제 부산 GIS 원천
-- 데이터가 아니며, 파이프라인(규칙 라우터·RAG·프로필·메타)이 실제 SQL을
-- 실행해 결과를 반환하는지 검증하기 위한 최소 스키마와 예시 행을 담습니다.
--
-- 실서비스에서는 이 시드 대신 실제 원천 테이블을 적재하세요.
-- 멱등 실행: 매번 DROP 후 재생성합니다.

\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS "AL_D010_26_20250704" CASCADE;
DROP TABLE IF EXISTS "AL_D060_00_20250804" CASCADE;
DROP TABLE IF EXISTS "AL_D198_26260_20250115" CASCADE;
DROP TABLE IF EXISTS "AL_D198_26410_20250115" CASCADE;
DROP TABLE IF EXISTS "BND_ADM_DONG_PG" CASCADE;
DROP TABLE IF EXISTS "TL_KODIS_BAS_26_202507" CASCADE;
DROP TABLE IF EXISTS "pnu_def" CASCADE;
DROP TABLE IF EXISTS "table_metadata" CASCADE;
DROP TABLE IF EXISTS "column_metadata" CASCADE;
DROP TABLE IF EXISTS "llm_schema_catalog" CASCADE;

-- =========================================================================
-- 메타데이터 테이블
-- =========================================================================
CREATE TABLE "table_metadata" (
    schema_name  text NOT NULL DEFAULT 'public',
    table_name   text NOT NULL,
    display_name text,
    category     text,
    description  text,
    PRIMARY KEY (schema_name, table_name)
);

CREATE TABLE "column_metadata" (
    schema_name  text NOT NULL DEFAULT 'public',
    table_name   text NOT NULL,
    column_name  text NOT NULL,
    display_name text,
    description  text,
    data_type    text,
    unit         text,
    PRIMARY KEY (schema_name, table_name, column_name)
);

-- RAG 카탈로그 (mxbai-embed-large = 1024차원)
CREATE TABLE "llm_schema_catalog" (
    fqname       text PRIMARY KEY,
    kind         text,
    summary      text,
    summary_kw   text,
    embedding    vector(1024),
    summary_hash text,
    updated_at   timestamptz DEFAULT now()
);

-- =========================================================================
-- AL_D010_26_20250704 : 부산 건물통합정보 (주력 테이블)
-- =========================================================================
CREATE TABLE "AL_D010_26_20250704" (
    "A0"  text PRIMARY KEY,          -- 건물 고유 ID
    "A4"  text,                      -- 법정동명 (예: 부산광역시 금정구 구서동)
    "A5"  text,                      -- 지번
    "A9"  text,                      -- 건축물용도명
    "A11" text,                      -- 구조
    "A12" numeric,                   -- 건물면적(건축면적, ㎡)
    "A14" numeric,                   -- 연면적(㎡)
    "A15" numeric,                   -- 대지면적(㎡)
    "A16" numeric,                   -- 높이(m)
    "A19" text,                      -- 보조 코드
    "A24" text,                      -- 건물명
    "A25" text,                      -- 보조 용도
    "A26" integer,                   -- 지상층수
    geometry geometry(Point, 4326)
);

-- 구서동(금정구) 공동주택 및 기타
INSERT INTO "AL_D010_26_20250704"
  ("A0","A4","A5","A9","A11","A12","A14","A15","A16","A19","A24","A25","A26",geometry) VALUES
  ('D010-0001','부산광역시 금정구 구서동','1-10','공동주택','철근콘크리트구조',3200,42000,9000,72,'01','구서그린타워','아파트',24, ST_SetSRID(ST_MakePoint(129.0890,35.2450),4326)),
  ('D010-0002','부산광역시 금정구 구서동','1-11','공동주택','철근콘크리트구조',2600,31000,7000,60,'01','구서한신아파트','아파트',20, ST_SetSRID(ST_MakePoint(129.0895,35.2455),4326)),
  ('D010-0003','부산광역시 금정구 구서동','1-12','공동주택','철근콘크리트구조',1800,19000,4200,45,'01','구서동부아파트','아파트',15, ST_SetSRID(ST_MakePoint(129.0885,35.2445),4326)),
  ('D010-0004','부산광역시 금정구 구서동','2-3','단독주택','벽돌구조',120,240,180,8,'02','',NULL,2, ST_SetSRID(ST_MakePoint(129.0880,35.2440),4326)),
  ('D010-0005','부산광역시 금정구 구서동','2-4','제1종근린생활시설','철근콘크리트구조',300,1500,400,15,'03','구서상가',NULL,5, ST_SetSRID(ST_MakePoint(129.0882,35.2448),4326)),
  ('D010-0006','부산광역시 금정구 구서동','2-5','단독주택','철근콘크리트구조',150,320,200,9,'02','',NULL,3, ST_SetSRID(ST_MakePoint(129.0878,35.2442),4326));

-- 장전동(금정구)
INSERT INTO "AL_D010_26_20250704"
  ("A0","A4","A5","A9","A11","A12","A14","A15","A16","A19","A24","A25","A26",geometry) VALUES
  ('D010-0011','부산광역시 금정구 장전동','100-1','공동주택','철근콘크리트구조',2900,36000,8000,66,'01','장전코오롱하늘채','아파트',22, ST_SetSRID(ST_MakePoint(129.0800,35.2300),4326)),
  ('D010-0012','부산광역시 금정구 장전동','100-2','공동주택','철근콘크리트구조',2200,25000,6000,54,'01','장전현대아파트','아파트',18, ST_SetSRID(ST_MakePoint(129.0805,35.2305),4326)),
  ('D010-0013','부산광역시 금정구 장전동','101-3','업무시설','철골철근콘크리트구조',900,7000,1500,40,'04','장전오피스',NULL,11, ST_SetSRID(ST_MakePoint(129.0795,35.2295),4326));

-- 우동(해운대구)
INSERT INTO "AL_D010_26_20250704"
  ("A0","A4","A5","A9","A11","A12","A14","A15","A16","A19","A24","A25","A26",geometry) VALUES
  ('D010-0021','부산광역시 해운대구 우동','1400-1','공동주택','철근콘크리트구조',4200,90000,12000,180,'01','해운대마린시티','아파트',48, ST_SetSRID(ST_MakePoint(129.1600,35.1600),4326)),
  ('D010-0022','부산광역시 해운대구 우동','1400-2','공동주택','철근콘크리트구조',3600,72000,10000,150,'01','해운대두산위브','아파트',40, ST_SetSRID(ST_MakePoint(129.1605,35.1605),4326)),
  ('D010-0023','부산광역시 해운대구 우동','1401-3','숙박시설','철근콘크리트구조',2500,45000,6000,120,'05','해운대관광호텔',NULL,30, ST_SetSRID(ST_MakePoint(129.1595,35.1595),4326)),
  ('D010-0024','부산광역시 해운대구 우동','1402-4','업무시설','철골구조',1500,20000,3000,80,'04','우동비즈타워',NULL,20, ST_SetSRID(ST_MakePoint(129.1610,35.1610),4326)),
  ('D010-0025','부산광역시 해운대구 우동','1403-5','제1종근린생활시설','철근콘크리트구조',350,1400,500,12,'03','우동프라자',NULL,4, ST_SetSRID(ST_MakePoint(129.1590,35.1590),4326));

-- 연산동(연제구)
INSERT INTO "AL_D010_26_20250704"
  ("A0","A4","A5","A9","A11","A12","A14","A15","A16","A19","A24","A25","A26",geometry) VALUES
  ('D010-0031','부산광역시 연제구 연산동','200-1','공동주택','철근콘크리트구조',2400,28000,6500,57,'01','연산더샵','아파트',19, ST_SetSRID(ST_MakePoint(129.0820,35.1830),4326)),
  ('D010-0032','부산광역시 연제구 연산동','200-2','공동주택','철근콘크리트구조',2000,21000,5000,48,'01','연산롯데캐슬','아파트',16, ST_SetSRID(ST_MakePoint(129.0825,35.1835),4326)),
  ('D010-0033','부산광역시 연제구 연산동','201-3','단독주택','벽돌구조',110,210,160,7,'02','',NULL,2, ST_SetSRID(ST_MakePoint(129.0815,35.1825),4326));

-- 안락동(동래구)
INSERT INTO "AL_D010_26_20250704"
  ("A0","A4","A5","A9","A11","A12","A14","A15","A16","A19","A24","A25","A26",geometry) VALUES
  ('D010-0041','부산광역시 동래구 안락동','300-1','공동주택','철근콘크리트구조',2100,23000,5500,51,'01','안락쌍용예가','아파트',17, ST_SetSRID(ST_MakePoint(129.1000,35.2000),4326)),
  ('D010-0042','부산광역시 동래구 안락동','300-2','교육연구시설','철근콘크리트구조',1200,6000,4000,20,'06','안락중학교',NULL,5, ST_SetSRID(ST_MakePoint(129.1005,35.2005),4326));

-- =========================================================================
-- BND_ADM_DONG_PG : 행정동 경계 (공간 포함 질의용)
-- =========================================================================
CREATE TABLE "BND_ADM_DONG_PG" (
    "ADM_CD" text,
    "ADM_NM" text,
    geometry geometry(Polygon, 4326)
);
INSERT INTO "BND_ADM_DONG_PG" ("ADM_CD","ADM_NM",geometry) VALUES
  ('2641056','구서1동', ST_SetSRID(ST_MakeEnvelope(129.085,35.240,129.093,35.250),4326)),
  ('2641057','장전1동', ST_SetSRID(ST_MakeEnvelope(129.076,35.226,129.084,35.234),4326)),
  ('2635051','우1동',  ST_SetSRID(ST_MakeEnvelope(129.155,35.155,129.165,35.165),4326)),
  ('2647053','연산1동', ST_SetSRID(ST_MakeEnvelope(129.078,35.179,129.086,35.187),4326)),
  ('2626054','안락1동', ST_SetSRID(ST_MakeEnvelope(129.096,35.196,129.104,35.204),4326));

-- =========================================================================
-- TL_KODIS_BAS_26_202507 : 기초구역
-- =========================================================================
CREATE TABLE "TL_KODIS_BAS_26_202507" (
    "BAS_ID"      text,
    "SIG_KOR_NM"  text,
    "BAS_AR"      numeric,
    geometry geometry(Polygon, 4326)
);
INSERT INTO "TL_KODIS_BAS_26_202507" ("BAS_ID","SIG_KOR_NM","BAS_AR",geometry) VALUES
  ('26410001','금정구',120000, ST_SetSRID(ST_MakeEnvelope(129.085,35.240,129.093,35.250),4326)),
  ('26410002','금정구',98000,  ST_SetSRID(ST_MakeEnvelope(129.076,35.226,129.084,35.234),4326)),
  ('26350001','해운대구',150000, ST_SetSRID(ST_MakeEnvelope(129.155,35.155,129.165,35.165),4326)),
  ('26470001','연제구',87000,  ST_SetSRID(ST_MakeEnvelope(129.078,35.179,129.086,35.187),4326)),
  ('26260001','동래구',76000,  ST_SetSRID(ST_MakeEnvelope(129.096,35.196,129.104,35.204),4326));

-- =========================================================================
-- AL_D060_00_20250804 : 산업단지
-- =========================================================================
CREATE TABLE "AL_D060_00_20250804" (
    "A0" text PRIMARY KEY,
    "A4" text,   -- 시군구코드
    "A8" text,   -- 단지명(후보1)
    "A9" text,   -- 단지명(후보2)
    geometry geometry(Polygon, 4326)
);
INSERT INTO "AL_D060_00_20250804" ("A0","A4","A8","A9",geometry) VALUES
  ('D060-01','26410','금정일반산업단지','금정일반산업단지', ST_SetSRID(ST_MakeEnvelope(129.090,35.246,129.092,35.248),4326)),
  ('D060-02','26440','부산과학일반산업단지','부산과학일반산업단지', ST_SetSRID(ST_MakeEnvelope(128.900,35.150,128.905,35.155),4326)),
  ('D060-03','26350','센텀일반산업단지','센텀일반산업단지', ST_SetSRID(ST_MakeEnvelope(129.125,35.170,129.130,35.175),4326));

-- =========================================================================
-- AL_D198_* : 구 용도별건물 (사용승인·허가일자 보유; 동래/금정)
-- =========================================================================
CREATE TABLE "AL_D198_26260_20250115" (
    "A0"  text PRIMARY KEY,
    "A4"  text,   -- 법정동명
    "A13" text,   -- 건물명
    "A7"  text,   -- 지번
    "A19" numeric,-- 연면적
    "A25" text,   -- 주요용도명
    "A28" text,
    "A29" text,
    "A33" text,   -- 허가일자
    "A34" text,   -- 사용승인일자
    geometry geometry(Point, 4326)
);
INSERT INTO "AL_D198_26260_20250115"
  ("A0","A4","A13","A7","A19","A25","A28","A29","A33","A34",geometry) VALUES
  ('D198D-01','부산광역시 동래구 안락동','안락쌍용예가','300-1',23000,'공동주택','1','주거','2003-05-01','2004-03-15', ST_SetSRID(ST_MakePoint(129.1000,35.2000),4326)),
  ('D198D-02','부산광역시 동래구 온천동','동래주민센터','50-2',6000,'공공용시설','5','공공용','1998-02-10','1999-01-20', ST_SetSRID(ST_MakePoint(129.0850,35.2050),4326)),
  ('D198D-03','부산광역시 동래구 안락동','안락중학교','300-2',6000,'교육연구시설','2','교육','1990-08-01','1991-03-02', ST_SetSRID(ST_MakePoint(129.1005,35.2005),4326));

CREATE TABLE "AL_D198_26410_20250115" (
    "A0"  text PRIMARY KEY,
    "A4"  text,
    "A13" text,
    "A7"  text,
    "A19" numeric,
    "A25" text,
    "A28" text,
    "A29" text,
    "A33" text,
    "A34" text,
    geometry geometry(Point, 4326)
);
INSERT INTO "AL_D198_26410_20250115"
  ("A0","A4","A13","A7","A19","A25","A28","A29","A33","A34",geometry) VALUES
  ('D198G-01','부산광역시 금정구 구서동','구서그린타워','1-10',42000,'공동주택','1','주거','2010-04-01','2011-06-10', ST_SetSRID(ST_MakePoint(129.0890,35.2450),4326)),
  ('D198G-02','부산광역시 금정구 장전동','장전코오롱하늘채','100-1',36000,'공동주택','1','주거','2014-09-01','2016-02-20', ST_SetSRID(ST_MakePoint(129.0800,35.2300),4326)),
  ('D198G-03','부산광역시 금정구 구서동','금정구청','2-1',12000,'공공용시설','5','공공용','1995-03-01','1996-05-15', ST_SetSRID(ST_MakePoint(129.0870,35.2430),4326));

-- =========================================================================
-- pnu_def : 필지 정의 참조 테이블 (RAG 카탈로그 대상)
-- =========================================================================
CREATE TABLE "pnu_def" (
    pnu   text PRIMARY KEY,
    sido  text,
    sigungu text,
    dong  text
);
INSERT INTO "pnu_def" (pnu,sido,sigungu,dong) VALUES
  ('2641010100','부산광역시','금정구','구서동'),
  ('2635010800','부산광역시','해운대구','우동');

-- =========================================================================
-- 테이블/컬럼 메타데이터
-- =========================================================================
INSERT INTO "table_metadata" (schema_name,table_name,display_name,category,description) VALUES
  ('public','AL_D010_26_20250704','GIS건물통합정보_부산광역시','건물','부산광역시 건물통합정보(용도·면적·높이·층수·위치)'),
  ('public','AL_D198_26260_20250115','용도별건물_동래구','건물','동래구 용도별 건물(사용승인·허가일자·주요용도명 포함)'),
  ('public','AL_D198_26410_20250115','용도별건물_금정구','건물','금정구 용도별 건물(사용승인·허가일자·주요용도명 포함)'),
  ('public','AL_D060_00_20250804','산업단지_부산광역시','산업단지','부산 산업단지 경계 및 단지명'),
  ('public','BND_ADM_DONG_PG','행정동경계_부산광역시','행정구역','부산 행정동 경계 폴리곤'),
  ('public','TL_KODIS_BAS_26_202507','기초구역_부산광역시','행정구역','부산 기초구역 경계 및 면적'),
  ('public','pnu_def','필지정의','참조','PNU 코드-행정구역 매핑 참조');

INSERT INTO "column_metadata" (schema_name,table_name,column_name,display_name,description,data_type,unit) VALUES
  ('public','AL_D010_26_20250704','A0','건물ID','건물 고유 식별자','text',NULL),
  ('public','AL_D010_26_20250704','A4','법정동명','건물이 속한 법정동명(시도·시군구·동)','text',NULL),
  ('public','AL_D010_26_20250704','A5','지번','토지 지번','text',NULL),
  ('public','AL_D010_26_20250704','A9','건축물용도명','건물의 주 용도명(공동주택·단독주택 등)','text',NULL),
  ('public','AL_D010_26_20250704','A11','구조','건물 구조(철근콘크리트 등)','text',NULL),
  ('public','AL_D010_26_20250704','A12','건물면적','건축면적','numeric','㎡'),
  ('public','AL_D010_26_20250704','A14','연면적','건물 전체 바닥면적 합','numeric','㎡'),
  ('public','AL_D010_26_20250704','A15','대지면적','대지 면적','numeric','㎡'),
  ('public','AL_D010_26_20250704','A16','높이','건물 높이','numeric','m'),
  ('public','AL_D010_26_20250704','A24','건물명','건물(단지) 명칭','text',NULL),
  ('public','AL_D010_26_20250704','A26','지상층수','지상 층수','integer','층'),
  ('public','AL_D198_26410_20250115','A25','주요용도명','대표 용도명','text',NULL),
  ('public','AL_D198_26410_20250115','A19','연면적','연면적','numeric','㎡'),
  ('public','AL_D198_26260_20250115','A25','주요용도명','대표 용도명','text',NULL),
  ('public','AL_D198_26260_20250115','A19','연면적','연면적','numeric','㎡'),
  ('public','TL_KODIS_BAS_26_202507','SIG_KOR_NM','시군구명','시군구 한글명','text',NULL),
  ('public','TL_KODIS_BAS_26_202507','BAS_AR','기초구역면적','기초구역 면적','numeric','㎡'),
  ('public','BND_ADM_DONG_PG','ADM_NM','행정동명','행정동 명칭','text',NULL);

ANALYZE "AL_D010_26_20250704";
ANALYZE "AL_D060_00_20250804";
ANALYZE "AL_D198_26260_20250115";
ANALYZE "AL_D198_26410_20250115";
ANALYZE "BND_ADM_DONG_PG";
ANALYZE "TL_KODIS_BAS_26_202507";
ANALYZE "table_metadata";
ANALYZE "column_metadata";
