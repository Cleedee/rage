# Análise do Projeto: Rage CCG Web

## 📋 Visão Geral

**rage-web** é uma aplicação web Flask para gerenciar cartas de um **Collectible Card Game (CCG)** chamado **Rage CCG**. A aplicação permite criar, listar, editar e excluir cartas (personagens, equipamentos e genéricas), além de gerenciar decks.

---

## 🏗️ Estrutura do Projeto

```
/workspace
├── app.py                          # Ponto de entrada da aplicação
├── pyproject.toml                  # Configuração do projeto Python (dependências)
├── docker-compose.yml              # Infraestrutura: Redis (desejado, mas não usado)
├── Makefile                        # Comandos auxiliares (flask run, docker)
├── NOTAS.txt                       # Links de referência (Flask, HTMX, Bulma, Redis OM)
├── README.md                       # Vazio
├── uv.lock                         # Lock file do gerenciador de pacotes uv
├── .python-version                 # Python 3.12
├── .gitignore
│
├── rage_web/                       # 📦 Pacote principal da aplicação
│   ├── __init__.py                 # Factory: create_app()
│   ├── config.py                   # Configurações (SQLite, SECRET_KEY)
│   ├── database.db                 # 🗄️ Banco SQLite (versionado!)
│   │
│   ├── ext/                        # Extensões
│   │   ├── base.py                 # Base declarativa do SQLAlchemy
│   │   ├── database.py             # Inicialização do SQLAlchemy
│   │   ├── cli.py                  # Comando CLI: flask init-database
│   │   └── repository.py          # Camada de repositório (CRUD)
│   │
│   ├── helpers/
│   │   └── forms.py                # Formulários WTForms
│   │
│   ├── models/                     # Modelos do banco
│   │   ├── card.py                 # Card (carta)
│   │   ├── deck.py                 # Deck
│   │   └── picture.py             # Picture (imagem)
│   │
│   ├── blueprints/                 # Blueprints (módulos)
│   │   ├── home/                   # Página inicial
│   │   ├── cards/                  # CRUD de cartas
│   │   └── decks/                  # CRUD de decks
│   │
│   ├── templates/
│   │   └── base.html              # Template base com Bulma + HTMX
│   │
│   └── instance/images/           # Imagens das cartas
│       └── hatii-the-thunderer.png
│
├── migrations/                     # Migrations Alembic
│   ├── alembic.ini
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 6bda8104262a_tabelas_iniciais.py
│
└── tests/
    ├── conftest.py                 # Fixtures pytest
    └── test_endpoints.py           # Testes (atualmente um só, quebrado)
```

---

## ⚙️ Stack Tecnológica

| Tecnologia | Uso |
|---|---|
| **Python 3.12** | Linguagem |
| **Flask 3.1.1** | Framework web |
| **Flask-SQLAlchemy 3.1.1** | ORM + banco de dados |
| **Flask-Migrate 4.1.0** | Migrations (Alembic) |
| **Flask-WTF 1.2.2** | Formulários + CSRF |
| **WTForms** | Definição de formulários |
| **SQLite** | Banco de dados |
| **Bulma CSS 1.0.4** | Framework CSS (via CDN) |
| **HTMX 1.9.10** | Interatividade AJAX (via CDN) |
| **Bootstrap Icons** | Ícones (via CDN) |
| **python-slugify** | Slug para nomes de arquivos |
| **pytest** | Testes |
| **uv** | Gerenciador de pacotes |

---

## 🗄️ Modelos de Dados

### Card (Carta) — `rage_web/models/card.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome da carta |
| `tipo` | String | Tipo: "Character", "Equipment" ou genérico |
| `rage` | Integer (default=0) | Atributo Fúria |
| `gnosis` | Integer (default=0) | Atributo Gnose |
| `health` | Integer (default=0) | Atributo Vitalidade |
| `rage_morph` | Integer (default=0) | Fúria em forma alternada |
| `gnosis_morph` | Integer (default=0) | Gnose em forma alternada |
| `health_morph` | Integer (default=0) | Vitalidade em forma alternada |
| `requires` | String (default='') | Requisitos (para equipamentos) |
| `keyword` | String (default='') | Palavras-chave |
| `text` | String (default='') | Texto/descrição/efeito |

### Deck — `rage_web/models/deck.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome do deck |
| `description` | String (nullable) | Descrição opcional |

### Picture (Imagem) — `rage_web/models/picture.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome do arquivo salvo |
| `side` | Integer (default=0) | 0 = frente, 1 = verso |
| `version` | String (nullable) | Versão da imagem |
| `card_id` | Integer (FK → card.id) | Relacionamento com Card |
| `card` | Relationship | Objeto Card relacionado |

---

## 🧭 Rotas / Endpoints

| Rota | Método | Funcionalidade |
|---|---|---|
| `/` | GET | Home |
| `/cards/new` | GET | Menu de criação (Character, Equipment, Card) |
| `/cards/new-character` | GET | Formulário de nova carta Character |
| `/cards/new-equipment` | GET | Formulário de nova carta Equipment |
| `/cards/new-card` | GET | Formulário de nova carta genérica |
| `/cards/new-character` | POST | Salvar nova carta Character |
| `/cards/new-equipment` | POST | Salvar nova carta Equipment |
| `/cards/card` | POST | Salvar carta genérica (+ imagem) |
| `/cards/character` | POST | Salvar/atualizar Character |
| `/cards/card/<id>` | GET | Visualizar/editar carta |
| `/cards/delete-card/<id>` | GET | Excluir carta |
| `/cards/search` | GET | Listar todas as cartas |
| `/decks/new` | GET | Formulário de novo deck |
| `/decks/search` | GET | Listar todos os decks |
| `/decks/deck` | POST | Salvar/atualizar deck |
| `/decks/deck/<id>` | GET | Visualizar/editar deck |
| `/decks/delete_deck/<id>` | GET | Excluir deck |

---

## 🔍 Pontos de Atenção / Problemas Identificados

1. **🏗️ `database.db` versionado** — O arquivo SQLite está dentro do pacote `rage_web/` e está sendo versionado no Git. Não é boa prática; o banco deve ficar em `instance/` ou ser ignorado.

2. **🐍 Inconsistência no formulário de Character** — O blueprint `cards` usa `CharacterCardForm` mas o formulário não tem campo `tipo`. Em `save_new_character()` o código tenta acessar `form.tipo.data` que não existe no formulário. Isso vai gerar erro ou salvar sem tipo.

3. **🔀 Rotas duplicadas / inconsistentes**:
   - `/new-character` tem GET e POST, mas também existe `/character` (POST) que faz a mesma coisa.
   - `/new-card` (GET) e `/card` (POST) vs `/new-equipment` (GET/POST).
   - Mistura de estilos: algumas rotas são RESTful, outras não.

4. **🧪 Testes quebrados** — O único teste (`test_endpoints.py`) espera `b"Hello, World!"` na resposta da home, mas a home renderiza um template vazio que estende `base.html`, sem essa string.

5. **📦 Redis configurado mas não implementado** — O `docker-compose.yml` sobe Redis, o `NOTAS.txt` menciona `redis-om-python`, mas Redis não é usado em lugar nenhum.

6. **🔒 `SECRET_KEY` hardcoded** — `"mysecretkey1234567890"` como fallback na configuração.

7. **📝 Imports não utilizados** — Em `blueprints/cards/__init__.py`, `PictureForm` e `secure_filename` são importados mas usados de forma incompleta ou não usados.

8. **🖼️ Upload de imagens incompleto** — O método `save_card()` (POST `/card`) tenta salvar imagem acessando `form.image.data`, mas o formulário `CardForm` não tem campo `image`. O template `picture.html` existe mas está sem rota vinculada (`save_picture` não existe como rota registrada).

9. **⚠️ `snippet_cards.html` obsoleto** — Usa `card.pk` em vez de `card.id`, indicando ser resquício de versão anterior (talvez Redis OM).

10. **🔄 Migrations vs Modelos** — A migration inicial está consistente com os modelos atuais.

11. **📝 Tratamento de erros inconsistente** — Mistura de `current_app.logger.error()` e `logging.error()`. `assert card is not None` pode gerar erros 500 em vez de 404.

12. **🔗 Relacionamento Card ↔ Picture** — O modelo `Picture` tem FK para `Card`, mas o blueprint de cards não implementa o upload de imagens nas rotas existentes.

---

## ✅ Pontos Positivos

- **Organização em Blueprints** — Separação clara de responsabilidades (home, cards, decks).
- **Uso de factory pattern** (`create_app()`) — Boa prática Flask.
- **Camada de repositório** — Abstração do banco em `ext/repository.py`.
- **Migrations com Alembic** — Controle de versão do schema.
- **Formulários WTForms com validação** — `DataRequired` nos campos obrigatórios.
- **Template base com Bulma + HTMX** — UI moderna sem muito JS customizado.
- **Extensões separadas** (`ext/`) — Código modular.
- **CLI command** `init-database` para setup inicial.

---

## 📦 Importação de Cartas (Concluído)

### Dados importados do LackeyCCG

**Fonte:** http://www.werepenguin.com/rage/lackey/

| Base | Cartas |
|---|---|
| `setinfo.txt` (oficiais) | 1.627 |
| `conclavetest.txt` (teste) | 44 |
| `hyplaytest.txt` (playtest) | 126 |
| **Total** | **1.797** |

**Comando de importação:**
```bash
flask import-cards          # Importa todas as fontes
flask import-cards --dry-run # Preview sem inserir
flask import-cards --fonte oficial  # Apenas oficiais
```

### Principais tipos de carta
Character (Gaia/Wyrm/Rogue), Gift, Equipment, Combat Action, Event, Ally, Enemy, Victim, Territory, Quest, Caern, Rite, Moot, Action

### Modelos atualizados
- **Card** — Novos campos: `expansion`, `image_file`, `sealed`, `notes`, `renown`, `damage`, `errata`
- **Deck** — Agora com relacionamento `cards` (muitos-para-muitos)
- **deck_cards** — Tabela associativa com `quantity`

---

## 🔮 Sugestões de Melhorias (Pendentes)

1. ~~Remover `database.db` do versionamento~~ ✅ (`.gitignore`)
2. ~~Corrigir formulário de Character~~ ✅ (campo `tipo` adicionado)
3. Padronizar as rotas — seguir um padrão RESTful consistente
4. ~~Corrigir testes~~ ✅ (18 testes passando)
5. Implementar upload de imagens completo com rotas e templates
6. ~~Adicionar relacionamento Deck ↔ Card~~ ✅ (tabela `deck_cards`)
7. Implementar Redis se for realmente necessário, ou remover do docker-compose
8. Adicionar autenticação (sign up / log in estão no template mas não implementados)
9. Usar variáveis de ambiente para SECRET_KEY em produção
10. Adicionar validação e tratamento de erros mais robustos (páginas 404, flash messages consistentes)
