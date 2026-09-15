-- ============================================================
-- Script de recreation complete de la base mock MISDW
-- (pour le conteneur Docker SQL Server)
-- ============================================================

CREATE DATABASE MISDW;
GO

USE MISDW;
GO

CREATE SCHEMA TRG;
GO
CREATE SCHEMA GO_AML;
GO
CREATE SCHEMA MASTER_DATA;
GO
CREATE SCHEMA HIST;
GO

-- Login applicatif (identique a celui utilise dans src/config.py)
CREATE LOGIN mis_amrihani WITH PASSWORD = 'mis_amrihani', CHECK_POLICY = OFF;
GO
CREATE USER mis_amrihani FOR LOGIN mis_amrihani;
GO
ALTER ROLE db_owner ADD MEMBER mis_amrihani;
GO

-- ============================================================
-- BLOC 2 : Client / Compte (base)
-- ============================================================

CREATE TABLE TRG.T24_FBNK_CUSTOMER (
    CUSTOMER_CODE       VARCHAR(50)  PRIMARY KEY,
    CUSTOMER_NO         VARCHAR(50),
    L_NATURE_CLIENT     VARCHAR(10),
    NAME_1              VARCHAR(200)
);
GO

CREATE TABLE TRG.T24_FBNK_ACCOUNT (
    ACCOUNT_NUMBER      VARCHAR(50)  PRIMARY KEY,
    ARRANGEMENT_ID      VARCHAR(50),
    MANDATE_RECORD      VARCHAR(200),
    ALT_ACCT_ID         VARCHAR(50),
    CURRENCY            VARCHAR(10),
    CATEGORY            VARCHAR(20),
    WORKING_BALANCE     DECIMAL(18,3),
    OPENING_DATE        VARCHAR(20),
    CUSTOMER_NO         VARCHAR(50)
);
GO

CREATE TABLE TRG.T24_FATB_ACCOUNT_CLOSED (
    ACCOUNT_NO          VARCHAR(50)  PRIMARY KEY,
    CUSTOMER_ID         VARCHAR(50),
    ACCT_CLOSE_DATE     VARCHAR(20)
);
GO

CREATE TABLE TRG.T24_FATB_ALTERNATE_ACCO000 (
    GLOBUS_ACCT_NUMBER   VARCHAR(50),
    ALTERNATIVE_NUMBER   VARCHAR(50)
);
GO

CREATE TABLE TRG.EQA_ACC_EXTERNAL_ACCOUNT_NUMBER (
    NEAB   VARCHAR(20),
    NEAN   VARCHAR(20),
    NEAS   VARCHAR(20),
    NEEAN  VARCHAR(50)
);
GO

CREATE TABLE GO_AML.ACCOUNT_TYPE_EQ_T24 (
    ACCOUNT_TYPE_T24    VARCHAR(20),
    ACCOUNT_TYPE_EQ     VARCHAR(20)
);
GO

CREATE TABLE GO_AML.ACCOUNT_TYPE (
    ACCOUNT_TYPE_ATB       VARCHAR(20),
    Description_ATB        VARCHAR(100),
    ACCOUNT_TYPE_goAML     VARCHAR(20)
);
GO

-- ============================================================
-- BLOC 3 : Transactions T24 (Caisse / Unknown)
-- ============================================================

CREATE TABLE TRG.T24_FATB_STMT_ENTRY_2024 (
    SYSTEM_ID           VARCHAR(20),
    ACCOUNT_NUMBER      VARCHAR(50),
    TRANS_REFERENCE     VARCHAR(50),
    VALUE_DATE          VARCHAR(20),
    SYSTEM_DATE_TIME    VARCHAR(30),
    CURRENCY            VARCHAR(10),
    AMOUNT_LCY          DECIMAL(18,3),
    AMOUNT_FCY          DECIMAL(18,3),
    TRANSACTION_CODE    VARCHAR(20)
);
GO

CREATE TABLE GO_AML.EQA_ACCOUNT_DAILY (
    BRN_ACC             VARCHAR(20),
    BN                  VARCHAR(20),
    SFX_ACC             VARCHAR(20),
    EQA_BALANCE_CCY     DECIMAL(18,3),
    CUST_TYPE_CODE      VARCHAR(20),
    RIB                 VARCHAR(50),
    CURRENCY_DESC       VARCHAR(10),
    CURRENCY_CODE       VARCHAR(10),
    ACCOUNT_NAME        VARCHAR(200),
    ACOUNT_TYPE_CODE    VARCHAR(20),
    OPENED              INT,
    CLOSED              INT,
    STATUS              VARCHAR(10)
);
GO

-- ============================================================
-- BLOC 4 : Virement
-- ============================================================

CREATE TABLE HIST.EQA_POSTINGS_2024 (
    SAPBR       VARCHAR(20),
    SADRF       VARCHAR(20),
    SAPSQ       VARCHAR(20),
    SAPOD       INT,
    SATSTP      DATETIME,
    SACCY       VARCHAR(10),
    SAAMA       DECIMAL(18,3),
    SATCD       VARCHAR(20),
    SAAB        VARCHAR(20),
    SAAN        VARCHAR(20),
    SAAS        VARCHAR(20)
);
GO

CREATE TABLE TRG.EQA_TRANSACTION_CODE (
    CTTCD   VARCHAR(20),
    CTTCN   VARCHAR(200)
);
GO

CREATE TABLE HIST.EQA_CURRENCIES_2024 (
    C8CCY   VARCHAR(10),
    C8SPT   DECIMAL(18,6),
    C8PWD   DECIMAL(18,6),
    C8CED   INT
);
GO

CREATE TABLE GO_AML.IBANK_VIREMENT_EMIS_MEME_BQE (
    BRN_ACC             VARCHAR(20),
    ACCOUNT_ID          VARCHAR(20),
    SFX_ACC             VARCHAR(20),
    POSTING_REF         VARCHAR(20),
    POSTING_DATE        DATE,
    COD_DEV             VARCHAR(10),
    LOCAL_AMOUNT        DECIMAL(18,3),
    TRANSACTION_NUMBER  VARCHAR(20),
    TRANS_CODE_DESC     VARCHAR(200),
    TRANS_CODE          VARCHAR(20),
    BENIF_NYMCPT        VARCHAR(50),
    BENIF_OPE           VARCHAR(200)
);
GO

-- ============================================================
-- BLOC 5 : Personnes liees au compte (EQ_PPH / EQ_TIERS)
-- ============================================================

CREATE TABLE GO_AML.T24_OCCUPATION (
    CODE     VARCHAR(10),
    LIBELLE  VARCHAR(200)
);
GO

CREATE TABLE GO_AML.EQ_PPH (
    CUSTOMER_CODE   VARCHAR(20),
    GENDER          VARCHAR(5),
    GIVEN_NAMES     VARCHAR(100),
    FAMILY_NAME     VARCHAR(100),
    DATE_OF_BIRTH   VARCHAR(10),
    PLACE_OF_BIRTH  VARCHAR(100),
    LEGAL_DOC_NAME  VARCHAR(50),
    LEGAL_ID        VARCHAR(50),
    LEGAL_ISS_AUTH  VARCHAR(50),
    LEGAL_ISS_DATE  VARCHAR(20),
    LEGAL_EXP_DATE  VARCHAR(20),
    NATIONALITY     VARCHAR(10),
    RESIDENCE       VARCHAR(10),
    STREET          VARCHAR(200),
    ADDRESS         VARCHAR(200),
    POST_CODE       VARCHAR(20),
    COUNTRY         VARCHAR(10),
    OCCUPATION      VARCHAR(20)
);
GO

CREATE TABLE GO_AML.EQ_TIERS (
    BASIC_N            VARCHAR(20),
    L_NATURE_CLIENT     VARCHAR(10),
    GENDER              VARCHAR(5),
    GIVEN_NAMES         VARCHAR(100),
    FAMILY_NAME         VARCHAR(100),
    DATE_OF_BIRTH       VARCHAR(10),
    [L PLACE OF BIRT]   VARCHAR(100),
    LEGAL_DOC_NAME      VARCHAR(50),
    LEGAL_ID            VARCHAR(50),
    LEGAL_ISS_AUTH      VARCHAR(50),
    LEGAL_ISS_DATE      VARCHAR(20),
    LEGAL_EXP_DATE      VARCHAR(20),
    NATIONALITY         VARCHAR(10),
    RESIDENCE           VARCHAR(10),
    STREET              VARCHAR(200),
    ADDRESS             VARCHAR(200),
    POST_CODE           VARCHAR(20),
    COUNTRY             VARCHAR(10),
    OCCUPATION          VARCHAR(20),
    TYPE_TIERS          VARCHAR(30)
);
GO

-- ============================================================
-- BLOC 6 : Carte
-- ============================================================

CREATE TABLE TRG.ATM_CUSTOMER_CARDHOLDER (
    CUS_IDEN        VARCHAR(20),
    CUS_CODE        VARCHAR(20),
    CUS_FIRS_NAM1   VARCHAR(100),
    CUS_FIRS_IDE1   VARCHAR(50)
);
GO

CREATE TABLE TRG.ATM_CARDS (
    CAR_NUMB        VARCHAR(30),
    CAR_CUS_CODE    VARCHAR(20)
);
GO

CREATE TABLE TRG.ATM_AUTHORIZATION (
    AUT_ACCO_ID1_F102              VARCHAR(20),
    AUT_PRIM_ACCT_NUMB_F002        VARCHAR(30),
    AUT_CARD_ACCP_TERM_ID_F041     VARCHAR(20),
    AUT_SYST_TRAC_AUDIT_NUMB_F011  VARCHAR(20),
    AUT_RESP_SYST_TIME             DATETIME,
    AUT_BILL_AMOU_F006             DECIMAL(18,3),
    AUT_BILL_AMOU_FEES_F008        DECIMAL(18,3),
    AUT_ADDI_AMOU_F054_CURR_CODE2  VARCHAR(10),
    AUT_REQU_SYST_TIME             DATETIME,
    AUT_CARD_ACCP_NAME_LOC_F043    VARCHAR(200)
);
GO

CREATE TABLE GO_AML.CURRENCY_CODES (
    AlphabeticCode  VARCHAR(10),
    NumericCode     INT,
    MinorUnit       INT
);
GO

-- ============================================================
-- BLOC 7 : Cheque
-- ============================================================

CREATE TABLE GO_AML.IBANK_CHEQUE_EMIS_MEME_BQE (
    BRN_ACC             VARCHAR(20),
    ACCOUNT_ID          VARCHAR(20),
    SFX_ACC             VARCHAR(20),
    POSTING_REF         VARCHAR(20),
    POSTING_DATE        DATE,
    COD_DEV             VARCHAR(10),
    MNT_OPE             DECIMAL(18,3),
    TRANS_CODE_DESC     VARCHAR(200),
    TRANS_CODE          VARCHAR(20),
    BENIF_NUMCPT        VARCHAR(50),
    BEN_OPE             VARCHAR(200)
);
GO

-- ============================================================
-- BLOC 8 : Effet
-- ============================================================

CREATE TABLE TRG.IBANK_RF_BANQUE (
    COD_BQE      VARCHAR(10),
    LIB_LON_BQE  VARCHAR(200)
);
GO

CREATE TABLE MASTER_DATA.T24_MAPPING_RIB (
    RIB   VARCHAR(30)
);
GO

CREATE TABLE TRG.IBANK_IB_REGLEMENT_EFFET (
    COD_DEV       VARCHAR(10),
    mnt_eff       DECIMAL(18,3),
    DAT_JOU       DATE,
    ref_ope       VARCHAR(50),
    num_cpt       VARCHAR(20),
    CPT_EQA       VARCHAR(20),
    num_seq_ope   VARCHAR(20),
    cod_age       VARCHAR(10),
    EQUATION      VARCHAR(50),
    rib_tir       VARCHAR(30),
    ORACLE        VARCHAR(20),
    ben_ope       VARCHAR(200),
    cod_bqe       VARCHAR(10)
);
GO


-- ============================================================
-- DONNEES MOCK - Client / Compte de test
-- ============================================================

INSERT INTO TRG.T24_FBNK_CUSTOMER (CUSTOMER_CODE, CUSTOMER_NO, L_NATURE_CLIENT, NAME_1)
VALUES ('CUST0001', 'CUST0001', 'PPH', 'BEN ALI Mohamed');
GO

INSERT INTO TRG.T24_FBNK_ACCOUNT
    (ACCOUNT_NUMBER, ARRANGEMENT_ID, MANDATE_RECORD, ALT_ACCT_ID, CURRENCY, CATEGORY, WORKING_BALANCE, OPENING_DATE, CUSTOMER_NO)
VALUES
    ('10001', 'ARR0001', '', 'TN591000000012345678', 'TND', '1001', 15000.500, '20230115', 'CUST0001');
GO

INSERT INTO TRG.T24_FATB_ALTERNATE_ACCO000 (GLOBUS_ACCT_NUMBER, ALTERNATIVE_NUMBER)
VALUES ('10001', '5009000004100');
GO

INSERT INTO GO_AML.ACCOUNT_TYPE_EQ_T24 (ACCOUNT_TYPE_T24, ACCOUNT_TYPE_EQ)
VALUES ('1001', 'EQ1001');
GO

INSERT INTO GO_AML.ACCOUNT_TYPE (ACCOUNT_TYPE_ATB, Description_ATB, ACCOUNT_TYPE_goAML)
VALUES ('EQ1001', 'Compte courant particulier', 'A');
GO

-- ============================================================
-- DONNEES MOCK - Transactions Caisse (T24) + Unknown
-- ============================================================

INSERT INTO TRG.T24_FATB_STMT_ENTRY_2024
    (SYSTEM_ID, ACCOUNT_NUMBER, TRANS_REFERENCE, VALUE_DATE, SYSTEM_DATE_TIME, CURRENCY, AMOUNT_LCY, AMOUNT_FCY, TRANSACTION_CODE)
VALUES
    ('TT', '10001', 'REF0001', '20240315', '2024-03-15 09:30', 'TND', 500.000, 500.000, '1017'),
    ('TT', '10001', 'REF0002', '20240320', '2024-03-20 14:12', 'TND', 1200.000, 1200.000, '1017'),
    ('TT', '10001', 'REF0003', '20240402', '2024-04-02 11:05', 'TND', 300.000, 300.000, '9999');
GO

INSERT INTO GO_AML.EQA_ACCOUNT_DAILY
    (BRN_ACC, BN, SFX_ACC, EQA_BALANCE_CCY, CUST_TYPE_CODE, RIB, CURRENCY_DESC, CURRENCY_CODE, ACCOUNT_NAME, ACOUNT_TYPE_CODE, OPENED, CLOSED, STATUS)
VALUES
    ('500', '9000004', '100', 15000.500, 'HB', 'TN591000000012345678', 'TND', 'TND', 'BEN ALI Mohamed', 'EQ1001', 1230115, NULL, 'A');
GO

-- ============================================================
-- DONNEES MOCK - Virement
-- ============================================================

INSERT INTO TRG.EQA_TRANSACTION_CODE (CTTCD, CTTCN)
VALUES ('021', 'Virement Emis'), ('427', 'Retrait GAB'), ('515', 'Encaissement CHQ'), ('223', 'Paiement effet');
GO

INSERT INTO HIST.EQA_CURRENCIES_2024 (C8CCY, C8SPT, C8PWD, C8CED)
VALUES ('TND', 1.000000, 1.000000, 3);
GO

INSERT INTO HIST.EQA_POSTINGS_2024
    (SAPBR, SADRF, SAPSQ, SAPOD, SATSTP, SACCY, SAAMA, SATCD, SAAB, SAAN, SAAS)
VALUES
    ('TLVIR', 'VIR0001', '1', 1240402, '2024-04-02 10:00', 'TND', 500.000, '021', '500', '9000004', '100'),
    ('@@O2', 'S000123AUD001', '1', 1240402, '2024-04-02 09:00', 'TND', 200000, '427', '500', '9000004', '100'),
    ('AS01', 'CHQ0001', '1', 1240402, '2024-04-02 10:30', 'TND', 150000, '515', '500', '9000004', '100'),
    ('TLEFF', 'EFF0001', '1', 1240402, '2024-04-02 11:00', 'TND', 350000, '223', '500', '9000004', '100');
GO

INSERT INTO GO_AML.IBANK_VIREMENT_EMIS_MEME_BQE
    (BRN_ACC, ACCOUNT_ID, SFX_ACC, POSTING_REF, POSTING_DATE, COD_DEV, LOCAL_AMOUNT, TRANSACTION_NUMBER, TRANS_CODE_DESC, TRANS_CODE, BENIF_NYMCPT, BENIF_OPE)
VALUES
    ('500', '9000004', '100', 'VIR0001', '2024-04-02', 'TND', 500.000, 'TRX0001', 'Virement Emis', '021', '', 'Virement mensuel');
GO

-- ============================================================
-- DONNEES MOCK - Personnes liees au compte
-- ============================================================

INSERT INTO GO_AML.T24_OCCUPATION (CODE, LIBELLE)
VALUES ('0001', 'EMPLOYE');
GO

INSERT INTO GO_AML.EQ_PPH
    (CUSTOMER_CODE, GENDER, GIVEN_NAMES, FAMILY_NAME, DATE_OF_BIRTH, PLACE_OF_BIRTH,
     LEGAL_DOC_NAME, LEGAL_ID, LEGAL_ISS_AUTH, LEGAL_ISS_DATE, LEGAL_EXP_DATE,
     NATIONALITY, RESIDENCE, STREET, ADDRESS, POST_CODE, COUNTRY, OCCUPATION)
VALUES
    ('9000004', 'M', 'Mohamed', 'BEN ALI', '19800115', 'TUNIS',
     'CIN', '12345678', 'TN', '20100101', '20300101',
     'TN', 'TN', '9 RUE HABIB BOURGUIBA', 'TUNIS', '1000', 'TN', '0001');
GO

INSERT INTO GO_AML.EQ_TIERS
    (BASIC_N, L_NATURE_CLIENT, GENDER, GIVEN_NAMES, FAMILY_NAME, DATE_OF_BIRTH, [L PLACE OF BIRT],
     LEGAL_DOC_NAME, LEGAL_ID, LEGAL_ISS_AUTH, LEGAL_ISS_DATE, LEGAL_EXP_DATE,
     NATIONALITY, RESIDENCE, STREET, ADDRESS, POST_CODE, COUNTRY, OCCUPATION, TYPE_TIERS)
VALUES
    ('9000004', 'PPH', 'M', 'Mohamed', 'BEN ALI', '19800115', 'TUNIS',
     'CIN', '12345678', 'TN', '20100101', '20300101',
     'TN', 'TN', '9 RUE HABIB BOURGUIBA', 'TUNIS', '1000', 'TN', '0001', 'SIGNATAIRE');
GO

-- ============================================================
-- DONNEES MOCK - Carte
-- ============================================================

INSERT INTO TRG.EQA_ACC_EXTERNAL_ACCOUNT_NUMBER (NEAB, NEAN, NEAS, NEEAN)
VALUES ('500', '9000004', '100', 'ORA1234567');
GO

INSERT INTO GO_AML.CURRENCY_CODES (AlphabeticCode, NumericCode, MinorUnit)
VALUES ('TND', 788, 3);
GO

INSERT INTO TRG.ATM_CUSTOMER_CARDHOLDER (CUS_IDEN, CUS_CODE, CUS_FIRS_NAM1, CUS_FIRS_IDE1)
VALUES ('ORA1234567', 'CH0001', 'BEN ALI Mohamed', '12345678');
GO

INSERT INTO TRG.ATM_CARDS (CAR_NUMB, CAR_CUS_CODE)
VALUES ('4000123456789012', 'CH0001');
GO

INSERT INTO TRG.ATM_AUTHORIZATION
    (AUT_ACCO_ID1_F102, AUT_PRIM_ACCT_NUMB_F002, AUT_CARD_ACCP_TERM_ID_F041, AUT_SYST_TRAC_AUDIT_NUMB_F011,
     AUT_RESP_SYST_TIME, AUT_BILL_AMOU_F006, AUT_BILL_AMOU_FEES_F008, AUT_ADDI_AMOU_F054_CURR_CODE2,
     AUT_REQU_SYST_TIME, AUT_CARD_ACCP_NAME_LOC_F043)
VALUES
    ('ORA1234567', '4000123456789012', '000123', 'AUD001',
     '2024-04-02 09:00', 200.000, 0.000, '788',
     '2024-04-02 09:00', 'TUNIS');
GO

-- ============================================================
-- DONNEES MOCK - Cheque
-- ============================================================

INSERT INTO GO_AML.IBANK_CHEQUE_EMIS_MEME_BQE
    (BRN_ACC, ACCOUNT_ID, SFX_ACC, POSTING_REF, POSTING_DATE, COD_DEV, MNT_OPE, TRANS_CODE_DESC, TRANS_CODE, BENIF_NUMCPT, BEN_OPE)
VALUES
    ('500', '9000004', '100', 'CHQ0001', '2024-04-02', 'TND', 150.000, 'Encaissement CHQ', '515', '', 'Encaissement cheque client');
GO

-- ============================================================
-- DONNEES MOCK - Effet
-- ============================================================

INSERT INTO TRG.IBANK_RF_BANQUE (COD_BQE, LIB_LON_BQE)
VALUES ('01', 'ARAB TUNISIAN BANK');
GO

INSERT INTO TRG.IBANK_IB_REGLEMENT_EFFET
    (COD_DEV, mnt_eff, DAT_JOU, ref_ope, num_cpt, CPT_EQA, num_seq_ope, cod_age, EQUATION, rib_tir, ORACLE, ben_ope, cod_bqe)
VALUES
    ('TND', 350.000, '2024-04-02', 'EFF0001', 'ORA1234567', '5009000004100', '1', '500', '', '01591000000012345678', '', 'Reglement effet fournisseur', '01');
GO

PRINT 'Base MISDW recreee avec succes (schemas, tables, donnees mock).';
GO
