import os
import re
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import quote

from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from database import conectar, inicializar_banco

BASE_DIR = Path(__file__).resolve().parent.parent
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ellencocheck-dev-secret-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
CORS(app, supports_credentials=True)

RESET_TOKEN_EXPIRY_MINUTES = int(os.environ.get("RESET_TOKEN_EXPIRY_MINUTES", "30"))

def agora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def erro(status, mensagem, detalhes=None):
    body = {"erro": mensagem, "message": mensagem}
    if detalhes:
        body["detalhes"] = detalhes
    return jsonify(body), status

def email_valido(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))

def usuario_json(row):
    return {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "ativo": bool(row["ativo"]),
        "criado_em": row["criado_em"],
        # aliases para facilitar integração com frontends diferentes
        "name": row["nome"],
        "createdAt": row["criado_em"],
    }

def autenticado(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return erro(401, "Faça login para continuar.")
        return fn(*args, **kwargs)
    return wrapper

# ------------------------- FRONTEND -------------------------

@app.route("/")
def inicio():
    return send_from_directory(BASE_DIR, "loginecadastro.html")

@app.route("/<path:arquivo>")
def arquivos(arquivo):
    if arquivo.startswith("api/"):
        return erro(404, "Recurso não encontrado.")
    caminho = BASE_DIR / arquivo
    if caminho.is_file():
        return send_from_directory(BASE_DIR, arquivo)
    return send_from_directory(BASE_DIR, "loginecadastro.html")

# ------------------------- LOGIN / CADASTRO -------------------------

@app.route("/api/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or dados.get("password") or "")

    if not email or not senha:
        return erro(400, "E-mail e senha são obrigatórios.")
    if not email_valido(email):
        return erro(400, "Informe um e-mail válido.")

    conn = conectar()
    try:
        usuario = conn.execute(
            "SELECT * FROM usuarios WHERE LOWER(email)=? AND ativo=1 LIMIT 1",
            (email,)
        ).fetchone()

        if not usuario:
            return erro(401, "E-mail ou senha incorretos.")

        senha_ok = False
        try:
            senha_ok = check_password_hash(usuario["senha"], senha)
        except Exception:
            senha_ok = False

        # Compatibilidade com banco antigo que eventualmente tenha senha em texto.
        if not senha_ok and usuario["senha"] == senha:
            senha_ok = True
            conn.execute(
                "UPDATE usuarios SET senha=? WHERE id=?",
                (generate_password_hash(senha), usuario["id"])
            )
            conn.commit()

        if not senha_ok:
            return erro(401, "E-mail ou senha incorretos.")

        session.clear()
        session.permanent = True
        session["usuario_id"] = usuario["id"]

        dados_usuario = usuario_json(usuario)
        return jsonify({
            "mensagem": "Login realizado com sucesso!",
            "message": "Login realizado com sucesso!",
            "usuario": dados_usuario
        })
    finally:
        conn.close()

@app.route("/api/logout", methods=["POST"])
@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensagem": "Logout realizado com sucesso."})

@app.route("/api/auth/me")
def me():
    uid = session.get("usuario_id")
    if not uid:
        return erro(401, "Nenhum usuário autenticado.")
    conn = conectar()
    try:
        usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not usuario:
            session.clear()
            return erro(401, "Nenhum usuário autenticado.")
        return jsonify(usuario_json(usuario))
    finally:
        conn.close()

@app.route("/api/usuarios", methods=["POST"])
@app.route("/api/auth/register", methods=["POST"])
def criar_usuario():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome") or dados.get("name") or "").strip()
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or dados.get("password") or "")

    if not nome or not email or not senha:
        return erro(400, "Preencha todos os campos obrigatórios.")
    if len(nome) > 150:
        return erro(400, "O nome deve ter no máximo 150 caracteres.")
    if not email_valido(email):
        return erro(400, "Informe um e-mail válido.")
    if len(senha) < 6:
        return erro(400, "A senha deve possuir pelo menos 6 caracteres.")

    conn = conectar()
    try:
        if conn.execute("SELECT 1 FROM usuarios WHERE LOWER(email)=?", (email,)).fetchone():
            return erro(409, "Este e-mail já está cadastrado.")

        cur = conn.execute(
            "INSERT INTO usuarios(nome,email,senha,ativo,criado_em) VALUES(?,?,?,?,?)",
            (nome, email, generate_password_hash(senha), 1, agora())
        )
        conn.commit()
        usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (cur.lastrowid,)).fetchone()

        return jsonify({
            "mensagem": "Usuário cadastrado com sucesso!",
            "usuario": usuario_json(usuario)
        }), 201
    finally:
        conn.close()

# ------------------------- CRUD DE USUÁRIOS -------------------------

@app.route("/api/usuarios", methods=["GET"])
@app.route("/api/users", methods=["GET"])
@autenticado
def listar_usuarios():
    conn = conectar()
    try:
        usuarios = conn.execute(
            "SELECT * FROM usuarios ORDER BY id"
        ).fetchall()
        return jsonify([usuario_json(u) for u in usuarios])
    finally:
        conn.close()

@app.route("/api/usuarios/<int:id>", methods=["GET"])
@app.route("/api/users/<int:id>", methods=["GET"])
@autenticado
def buscar_usuario(id):
    conn = conectar()
    try:
        u = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
        if not u:
            return erro(404, "Usuário não encontrado.")
        return jsonify(usuario_json(u))
    finally:
        conn.close()

@app.route("/api/usuarios/<int:id>", methods=["PUT"])
@app.route("/api/users/<int:id>", methods=["PUT"])
@autenticado
def atualizar_usuario(id):
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome") or dados.get("name") or "").strip()
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or dados.get("password") or "")

    if not nome or not email:
        return erro(400, "Nome e e-mail são obrigatórios.")
    if not email_valido(email):
        return erro(400, "Informe um e-mail válido.")
    if senha and len(senha) < 6:
        return erro(400, "A senha deve possuir pelo menos 6 caracteres.")

    conn = conectar()
    try:
        u = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
        if not u:
            return erro(404, "Usuário não encontrado.")

        outro = conn.execute(
            "SELECT 1 FROM usuarios WHERE LOWER(email)=? AND id<>?",
            (email, id)
        ).fetchone()
        if outro:
            return erro(409, "Este e-mail já está cadastrado por outro usuário.")

        novo_hash = generate_password_hash(senha) if senha else u["senha"]
        ativo = 1 if dados.get("ativo", u["ativo"]) else 0

        conn.execute(
            "UPDATE usuarios SET nome=?, email=?, senha=?, ativo=? WHERE id=?",
            (nome, email, novo_hash, ativo, id)
        )
        conn.commit()
        atualizado = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
        return jsonify({
            "mensagem": "Usuário atualizado com sucesso.",
            "usuario": usuario_json(atualizado)
        })
    finally:
        conn.close()

@app.route("/api/usuarios/<int:id>", methods=["DELETE"])
@app.route("/api/users/<int:id>", methods=["DELETE"])
@autenticado
def excluir_usuario(id):
    if id == session.get("usuario_id"):
        return erro(400, "Você não pode excluir o usuário que está logado.")

    conn = conectar()
    try:
        u = conn.execute("SELECT id FROM usuarios WHERE id=?", (id,)).fetchone()
        if not u:
            return erro(404, "Usuário não encontrado.")

        # Checklists dependem do usuário. Mantemos o histórico e apenas desativamos.
        conn.execute("UPDATE usuarios SET ativo=0 WHERE id=?", (id,))
        conn.commit()
        return jsonify({"mensagem": "Usuário desativado com sucesso."})
    finally:
        conn.close()

# ------------------------- EQUIPAMENTOS -------------------------

@app.route("/api/equipamentos", methods=["GET"])
def listar_equipamentos():
    conn = conectar()
    try:
        rows = conn.execute("""
            SELECT e.*, t.nome AS tipo_nome
            FROM equipamentos e
            LEFT JOIN tipos_equipamentos t ON t.id=e.tipo_id
            ORDER BY e.nome
        """).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.route("/api/equipamentos/<int:id>", methods=["GET"])
def buscar_equipamento(id):
    conn = conectar()
    try:
        row = conn.execute("""
            SELECT e.*, t.nome AS tipo_nome
            FROM equipamentos e
            LEFT JOIN tipos_equipamentos t ON t.id=e.tipo_id
            WHERE e.id=?
        """, (id,)).fetchone()
        if not row:
            return erro(404, "Equipamento não encontrado.")
        return jsonify(dict(row))
    finally:
        conn.close()

@app.route("/api/equipamentos/<int:id>/historico", methods=["GET"])
def historico_equipamento(id):
    conn = conectar()
    try:
        rows = conn.execute("""
            SELECT c.id, c.horimetro, c.status, c.observacoes,
                   c.realizado_em, u.nome AS operador
            FROM checklists c
            JOIN usuarios u ON u.id=c.usuario_id
            WHERE c.equipamento_id=?
            ORDER BY c.realizado_em DESC
        """, (id,)).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

# ------------------------- TIPOS / ITENS -------------------------

@app.route("/api/tipos-equipamentos", methods=["GET"])
def listar_tipos():
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT * FROM tipos_equipamentos WHERE ativo=1 ORDER BY nome"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.route("/api/itens-inspecao", methods=["GET"])
def listar_itens():
    tipo_id = request.args.get("tipo_id", type=int)
    conn = conectar()
    try:
        if tipo_id:
            rows = conn.execute("""
                SELECT * FROM itens_inspecao
                WHERE ativo=1 AND tipo_id=?
                ORDER BY categoria, ordem, nome
            """, (tipo_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM itens_inspecao
                WHERE ativo=1
                ORDER BY categoria, ordem, nome
            """).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

# ------------------------- CHECKLISTS -------------------------

@app.route("/api/checklists", methods=["POST"])
def criar_checklist():
    dados = request.get_json(silent=True) or {}
    equipamento_id = dados.get("equipamento_id")
    usuario_id = dados.get("usuario_id") or session.get("usuario_id")
    horimetro = dados.get("horimetro", 0)
    status = dados.get("status")
    observacoes = dados.get("observacoes")
    itens = dados.get("itens", [])

    if not equipamento_id or not usuario_id or not status:
        return erro(400, "Equipamento, usuário e status são obrigatórios.")
    if status not in ("APROVADO", "APROVADO_COM_OBSERVACAO", "REPROVADO"):
        return erro(400, "Status da inspeção inválido.")
    if not isinstance(itens, list):
        return erro(400, "Itens da inspeção inválidos.")

    conn = conectar()
    try:
        if not conn.execute("SELECT id FROM equipamentos WHERE id=?", (equipamento_id,)).fetchone():
            return erro(404, "Equipamento não encontrado.")
        if not conn.execute("SELECT id FROM usuarios WHERE id=?", (usuario_id,)).fetchone():
            return erro(404, "Usuário não encontrado.")

        cur = conn.execute("""
            INSERT INTO checklists(equipamento_id,usuario_id,horimetro,status,observacoes)
            VALUES(?,?,?,?,?)
        """, (equipamento_id, usuario_id, horimetro, status, observacoes))
        checklist_id = cur.lastrowid

        for item in itens:
            item_id = item.get("item_inspecao_id")
            item_status = item.get("status")
            if item_id and item_status:
                conn.execute("""
                    INSERT OR REPLACE INTO respostas_checklist
                    (checklist_id,item_inspecao_id,status,observacao)
                    VALUES(?,?,?,?)
                """, (checklist_id, item_id, item_status, item.get("observacao")))

        conn.execute(
            "UPDATE equipamentos SET horimetro=?, atualizado_em=CURRENT_TIMESTAMP WHERE id=?",
            (horimetro, equipamento_id)
        )
        conn.commit()
        return jsonify({
            "mensagem": "Checklist criado com sucesso!",
            "checklist_id": checklist_id
        }), 201
    except Exception as exc:
        conn.rollback()
        return erro(500, "Erro ao salvar checklist.", str(exc))
    finally:
        conn.close()

@app.route("/api/checklists", methods=["GET"])
def listar_checklists():
    conn = conectar()
    try:
        rows = conn.execute("""
            SELECT c.id, c.equipamento_id, e.nome AS equipamento,
                   c.usuario_id, u.nome AS operador, c.horimetro,
                   c.status, c.observacoes, c.realizado_em
            FROM checklists c
            JOIN equipamentos e ON e.id=c.equipamento_id
            JOIN usuarios u ON u.id=c.usuario_id
            ORDER BY c.realizado_em DESC
        """).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

# ------------------------- RECUPERAÇÃO DE SENHA -------------------------

def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

@app.route("/api/password/forgot", methods=["POST"])
def esqueci_senha():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email") or "").strip().lower()

    if not email or not email_valido(email):
        return erro(400, "Informe um e-mail válido.")

    conn = conectar()
    try:
        u = conn.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", (email,)).fetchone()
        if u:
            token = secrets.token_urlsafe(32)
            validade = (datetime.now(timezone.utc) +
                        timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)).isoformat()
            conn.execute("UPDATE password_reset_tokens SET used=1 WHERE user_id=? AND used=0", (u["id"],))
            conn.execute("""
                INSERT INTO password_reset_tokens(token_hash,user_id,expiry_date,used)
                VALUES(?,?,?,0)
            """, (hash_token(token), u["id"], validade))
            conn.commit()
            print("\n[RECUPERAÇÃO DE SENHA]")
            print("Link:", f"http://localhost:5000/reset-password.html?token={quote(token)}\n")

        return jsonify({
            "mensagem": "Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação."
        })
    finally:
        conn.close()

@app.route("/api/password/reset", methods=["POST"])
def redefinir_senha():
    dados = request.get_json(silent=True) or {}
    token = str(dados.get("token") or "")
    senha = str(dados.get("newPassword") or dados.get("senha") or "")

    if not token or len(senha) < 6:
        return erro(400, "Token e nova senha válida são obrigatórios.")

    conn = conectar()
    try:
        t = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash=?",
            (hash_token(token),)
        ).fetchone()

        if not t or t["used"]:
            return erro(409, "Token inválido ou já utilizado.")

        expira = datetime.fromisoformat(t["expiry_date"])
        if datetime.now(timezone.utc) > expira:
            return erro(409, "Este link de recuperação expirou.")

        conn.execute(
            "UPDATE usuarios SET senha=? WHERE id=?",
            (generate_password_hash(senha), t["user_id"])
        )
        conn.execute("UPDATE password_reset_tokens SET used=1 WHERE id=?", (t["id"],))
        conn.commit()
        return jsonify({"mensagem": "Senha redefinida com sucesso."})
    finally:
        conn.close()

@app.errorhandler(404)
def nao_encontrado(exc):
    if request.path.startswith("/api/"):
        return erro(404, "Recurso não encontrado.")
    return send_from_directory(BASE_DIR, "loginecadastro.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
