import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "frotacheck.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tipos_equipamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS equipamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    patrimonio TEXT UNIQUE,
    modelo TEXT,
    fabricante TEXT,
    placa TEXT,
    ano INTEGER,
    horimetro REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ATIVO'
        CHECK(status IN ('ATIVO','MANUTENCAO','INATIVO')),
    observacoes TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tipo_id) REFERENCES tipos_equipamentos(id)
);

CREATE TABLE IF NOT EXISTS itens_inspecao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    categoria TEXT NOT NULL DEFAULT 'Geral',
    ordem INTEGER NOT NULL DEFAULT 0,
    obrigatorio INTEGER NOT NULL DEFAULT 1,
    ativo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(tipo_id) REFERENCES tipos_equipamentos(id)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipamento_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    horimetro REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL
        CHECK(status IN ('APROVADO','APROVADO_COM_OBSERVACAO','REPROVADO')),
    observacoes TEXT,
    realizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id),
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS respostas_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id INTEGER NOT NULL,
    item_inspecao_id INTEGER NOT NULL,
    status TEXT NOT NULL
        CHECK(status IN ('OK','ATENCAO','PROBLEMA','NAO_APLICAVEL')),
    observacao TEXT,
    respondido_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(checklist_id, item_inspecao_id),
    FOREIGN KEY(checklist_id) REFERENCES checklists(id) ON DELETE CASCADE,
    FOREIGN KEY(item_inspecao_id) REFERENCES itens_inspecao(id)
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    expiry_date TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_checklists_equipamento ON checklists(equipamento_id);
CREATE INDEX IF NOT EXISTS idx_checklists_usuario ON checklists(usuario_id);
CREATE INDEX IF NOT EXISTS idx_itens_tipo ON itens_inspecao(tipo_id);
"""

SEED = """
INSERT OR IGNORE INTO tipos_equipamentos(id,nome,descricao,ativo) VALUES
(1,'Escavadeira','Máquina para escavação e movimentação de materiais',1),
(2,'Retroescavadeira','Equipamento para escavação e carregamento',1),
(3,'Pá Carregadeira','Máquina para carregamento e movimentação',1),
(4,'Motoniveladora','Máquina para nivelamento de terrenos',1),
(5,'Rolo Compactador','Equipamento para compactação',1);

INSERT OR IGNORE INTO equipamentos
(id,tipo_id,nome,patrimonio,modelo,fabricante,horimetro,status,ativo)
VALUES
(1,1,'Escavadeira 01','EQ-001','320','Caterpillar',1250.50,'ATIVO',1),
(2,2,'Retroescavadeira 01','EQ-002','416F2','Caterpillar',980.20,'ATIVO',1);

INSERT OR IGNORE INTO itens_inspecao
(id,tipo_id,nome,descricao,categoria,ordem,obrigatorio,ativo) VALUES
(1,1,'Nível do óleo do motor','Verificar se o nível está adequado.','Motor',1,1,1),
(2,2,'Nível do óleo do motor','Verificar se o nível está adequado.','Motor',1,1,1),
(4,1,'Nível do líquido de arrefecimento','Verificar nível e sinais de vazamento.','Motor',2,1,1),
(5,1,'Vazamentos hidráulicos','Verificar mangueiras, conexões e cilindros.','Hidráulica',3,1,1),
(6,1,'Estado das esteiras','Verificar desgaste, tensão e danos.','Material Rodante',4,1,1),
(7,2,'Pneus','Verificar calibragem, desgaste e danos.','Rodagem',2,1,1);
"""

def conectar():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def inicializar_banco():
    conn = conectar()
    try:
        conn.executescript(SCHEMA)
        conn.executescript(SEED)
        conn.commit()
    finally:
        conn.close()
