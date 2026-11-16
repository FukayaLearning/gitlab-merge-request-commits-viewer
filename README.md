# GitLab Merge Request Commits Viewer

OpenSpecのように「1サブタスク＝1コミット」で粒度を揃えて積み上げたGit履歴やMerge Requestに対し、**コミット単位の差分・目的（Why / What）・紐づくタスク情報・実行コマンド（Git Trailers）** を1画面（3ペイン構成）で高速に切り替えながら閲覧・レビューできるローカル実行Webアプリケーションです。

---

## 主な特徴

- **完全ゼロ依存（Zero-Dependency）**:
  - バックエンドは **Python 3 標準ライブラリのみ**（`http.server`, `subprocess`, `urllib.request`, `json`, `re`, `urllib.parse`）で動作し、`pip install` や `glab` CLI の事前導入は不要です。
  - フロントエンドは **ビルドレス Vanilla JS (ES Modules) + CSS + 同梱 Diff2Html** で構成され、`npm install` やビルド工程も不要です。
- **3ペイン高速レビューUI**:
  1. **ヘッダー（ターゲット選択）**: 現在のリポジトリ名・ブランチ表示、GitLab REST API v4 によるオープンMR一覧のドロップダウン選択（未認証・オフライン時はローカルの `base` / `head` ブランチ比較へ自動フォールバック）。
  2. **左ペイン（Commit Menu）**:
     - 時系列コミット一覧と変更種別バッジ（`🤖 Command` コマンド一括変更 / `✍️ Manual` 手動実装 / `✅ Test` テスト追加）およびOpenSpecタスクIDの自動表示。
     - キーボードの `j` / `k` または `↓` / `↑` キーによるページリロードなしの瞬時コミット切り替え。
     - コミット単位の「確認済み（Reviewed）」チェック管理（`r` キーまたはチェックボックス、`localStorage` にリポジトリ・SHA単位で永続化）。
  3. **中央・右ペイン（Commit Context & Diff Viewer）**:
     - 上部サマリカード：コミットの目的（`Why` / `What`）、OpenSpecタスク（`Task`）、検証内容（`Verification`）、および実行コマンド全文（`Executed-Command`）の強調表示。
     - 下部Diffビューア：変更ファイル一覧（クリックで該当ファイルへスクロール移動）と、**Split（左右分割）/ Unified（統合）** 切替・**空白無視（Ignore Whitespace）** オプション対応のシンタックスハイライト付きDiff表示。

---

## 動作要件

- **Python 3.8 以上**（標準ライブラリのみ使用）
- **Git CLI**（`git` コマンドが PATH に存在すること）
- **GitLab Access Token** *(任意)*：プライベートリポジトリや社内 GitLab のオープンMR一覧を API で取得する場合に設定します。未設定・オフライン時でもローカルブランチ間の比較ビューアとしてそのまま利用可能です。

---

## GitLab API トークン権限の設定手順

本ビューアは、ローカルリポジトリの `origin` リモート URL（HTTPS / SSH、サブグループ対応）から GitLab ホストとプロジェクトパスを自動検出し、GitLab REST API v4（`GET /api/v4/projects/:id/merge_requests?state=opened`）を実行してオープン MR 一覧を取得します。

### 必要な最小権限（スコープ）

- **`read_api`**（読み取り専用 API アクセス）
  - 本ビューアはオープン MR 一覧の取得のみを行うため、書き込み権限を含む `api` スコープは不要です。最小権限として **`read_api`** のみを付与してください。

### 1. Personal Access Token (PAT) を発行する場合（推奨）

ユーザー単位で複数のリポジトリを横断して利用する場合に適しています。

1. GitLab（`https://gitlab.com` またはセルフホスト GitLab）にログインします。
2. 右上のプロフィールアイコンをクリックし、**Preferences**（または **Edit profile**）を開きます。
3. 左メニューから **Access Tokens**（Personal Access Tokens）を選択します。
4. **Add new token** をクリックし、以下を設定します：
   - **Token name**: 任意の名前（例: `gitlab-mr-commits-viewer`）
   - **Expiration date**: 任意の有効期限
   - **Select scopes**: **`read_api`** にチェックを入れる
5. **Create personal access token** をクリックし、生成されたトークン（`glpat-...`）を控えます。

### 2. Project Access Token を発行する場合（特定リポジトリ限定）

特定プロジェクトのみに権限を限定したい場合に利用します（プロジェクトの Maintainer 以上、またはセルフホスト環境で Project Access Token が有効な場合）。

1. 対象の GitLab プロジェクトページを開きます。
2. 左メニューから **Settings** → **Access Tokens** を選択します。
3. **Add new token** をクリックし、以下を設定します：
   - **Token name**: 任意の名前（例: `mr-commits-viewer`）
   - **Select a role**: **Reporter** 以上（MR 閲覧権限が必要）
   - **Select scopes**: **`read_api`** にチェックを入れる
4. **Create project access token** をクリックし、生成されたトークンを控えます。

### 3. 環境変数の設定と起動

発行したトークンは環境変数 `GITLAB_TOKEN`（または `GITLAB_PRIVATE_TOKEN`）に設定して起動します。トークンは `PRIVATE-TOKEN` HTTP ヘッダーにのみ使用され、エラー出力や UI に露出することはありません。

```bash
# 基本（origin リモートから GitLab ホスト・プロジェクトを自動検出）
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
python3 server.py --repo /path/to/your/repo
```

セルフホスト GitLab や、リモート URL と異なるホスト・プロジェクトを指定したい場合は、以下の環境変数で上書きできます：

| 環境変数 | 必須 | 説明 |
| :--- | :--- | :--- |
| `GITLAB_TOKEN` | 任意 | GitLab Access Token（`read_api` スコープ）。`GITLAB_PRIVATE_TOKEN` も可 |
| `GITLAB_URL` | 任意 | GitLab ベース URL を明示指定（例: `https://gitlab.internal.example.com`） |
| `GITLAB_PROJECT_ID` | 任意 | プロジェクト ID（数値）またはパス（例: `group/subgroup/repo`）を明示指定 |
| `SSL_CERT_FILE` | 任意 | 社内自己署名 CA 証明書を使用する場合の PEM ファイルパス（Python `urllib` 用） |

> **フォールバック仕様**: トークン未設定（非公開プロジェクトで 401/403）、リモート未設定、オフライン、またはオープン MR が 0 件の場合はエラーで停止せず、ヘッダーに `Local mode (...)` を表示してローカルブランチ比較へ自動的に切り替わります。

---

## 起動方法

```bash
# カレントディレクトリのリポジトリを対象に起動（デフォルト: http://127.0.0.1:8000）
python3 server.py

# 任意のローカルGitリポジトリとポートを指定して起動
python3 server.py --repo /path/to/your/repo --port 8765

# 環境変数での指定にも対応
REPO_PATH=/path/to/your/repo PORT=8765 HOST=127.0.0.1 python3 server.py

# CLIヘルプの表示
python3 server.py --help
```

起動後、ブラウザで `http://127.0.0.1:8000`（または指定したホスト・ポート）を開きます。
※ MR のソース/ターゲットブランチがローカルに存在しない場合は、対象リポジトリで事前に `git fetch` を実行してください。

---

## キーボードショートカット

| キー | 動作 |
| :--- | :--- |
| `j` / `↓` | 次のコミットへ移動 |
| `k` / `↑` | 前のコミットへ移動 |
| `r` | 現在選択中のコミットの「確認済み（Reviewed）」をトグル |

---

## 自動解析されるコミットメッセージ形式（Git Trailers）

本ビューアは以下のフォーマットで記述されたコミットメッセージ本文・Git Trailersを自動抽出し、バッジ判定とサマリカード表示に利用します（通常のコミットメッセージもそのまま閲覧可能です）。

```text
feat(parser): add Git Trailers metadata parser

Why: コミットメッセージからタスクIDや実行コマンドを構造化抽出するため
What: viewer_backend/parser.py に正規表現パーサーと変更種別判定関数を実装

Issue: #12
Task: 1.1 [S01-03-02, S01-03-03]
Verification: python3 -m unittest tests/test_parser.py -v
Executed-Command: manual
```

- `Executed-Command` が `"manual"` 以外（例: `ruff check --fix .` や `sed -i ...`）の場合、左ペインに **`🤖 Command`** バッジが付与され、サマリカード上部に実行コマンド全文が強調表示されます。

---

## ディレクトリ構成

```text
.
├── README.md                 # プロジェクト概要・トークン権限設定・利用手順
├── AGENTS.md                 # AIエージェント向け開発・OpenSpec・コミット規約
├── server.py                 # Python標準ライブラリ製 HTTP / APIサーバー
├── viewer_backend/           # バックエンドモジュール
│   ├── __init__.py
│   ├── parser.py             # コミットメッセージ / Git Trailers パーサー
│   ├── gitlab_service.py     # GitLab REST API v4 連携・フォールバックサービス
│   └── git_service.py        # git サブプロセス実行サービス
├── static/                   # ビルドレスWebフロントエンド（3ペインUI）
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── vendor/diff2html/     # 同梱 Diff2Html アセット
├── tests/                    # 標準 unittest による単体・API統合テスト
└── openspec/                 # OpenSpec (USDMスキーマ) 仕様・変更管理
```

## テストの実行

```bash
python3 -m unittest discover -s tests -v
```
