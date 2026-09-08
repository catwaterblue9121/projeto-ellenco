# EllencoCheck — Python + Flask + SQLite

O projeto foi integrado com o CRUD de usuários em Python.

## Executar

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra **http://localhost:5000**.

## Banco

O banco `frotacheck.db` é criado automaticamente. Não é necessário XAMPP ou MySQL.

As tabelas originais do FrotaCheck foram mantidas:
- usuarios
- equipamentos
- tipos_equipamentos
- itens_inspecao
- checklists
- respostas_checklist

Também foram adicionados:
- password_reset_tokens
- CRUD completo de usuários
- sessão de login
- recuperação de senha

## Usuários

Depois de entrar no sistema, abra **http://localhost:5000/usuarios.html**.

A senha é armazenada com hash usando Werkzeug.

## API de usuários

- POST `/api/usuarios`
- GET `/api/usuarios`
- GET `/api/usuarios/<id>`
- PUT `/api/usuarios/<id>`
- DELETE `/api/usuarios/<id>`

Também existem aliases `/api/users/...` e `/api/auth/...` para facilitar integração.

O DELETE desativa o usuário em vez de apagar fisicamente, preservando o histórico dos checklists.
