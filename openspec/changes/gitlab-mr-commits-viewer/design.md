# Design

## Context

本リポジトリは新規立ち上げのローカル実行型コミットレビュービューアである。先行する `github-pull-request-commits-viewer` と同一のコンセプト（1サブタスク＝1コミットの構造化レビュー、完全ゼロ依存バックエンド、ビルドレス 3ペイン Web UI）を踏襲しつつ、PR/MR 一覧の取得手段を GitHub CLI (`gh`) から GitLab REST API v4 へ置き換える。詳細な動機は `proposal.md`、要求仕様は `usdm.md` および `specs/*/spec.md` を参照。

## Goals / Non-Goals

**Goals:**
- Python 3.8+ 標準ライブラリのみで動作するゼロ依存アーキテクチャの維持（`urllib.request` による GitLab REST API 呼び出し）。
- `git remote get-url origin` からの GitLab ホスト・サブグループ対応プロジェクトパス自動抽出、および `GITLAB_URL` / `GITLAB_PROJECT_ID` / `GITLAB_TOKEN` による柔軟な設定。
- トークン未設定・認証エラー・オフライン時でも停止しないローカルブランチ比較への自動フォールバック。
- ビルドレス Vanilla JS + CSS + 同梱 Diff2Html による 3ペイン高速レビュー UI。
- `README.md` における `read_api` トークン権限の発行・設定手順の明確化。

**Non-Goals:**
- GitLab への書き込み操作（MR へのコメント投稿、Approve、マージ、ステータス変更等）。
- `glab` CLI や外部 Python パッケージ（`requests`, `python-gitlab` 等）への依存。
- OAuth2 ログインフローやサーバー側へのトークン永続保存。

## Decisions

### 1. GitLab REST API 連携方式（`urllib.request` vs `glab` CLI / 外部ライブラリ）
- **決定**: Python 標準ライブラリの `urllib.request` を用いた専用モジュール `viewer_backend/gitlab_service.py` を実装する。
- **理由**: ユーザー指定のとおり「GitLab で API 実行」を実現しつつ、`pip install` や `glab` CLI の事前インストールを不要にするため。標準ライブラリのみで完結し、HTTP モックによる `unittest` も容易になる。
- **代替案**: `glab mr list` サブプロセス呼び出し（`glab` CLI 未導入環境で動かず、API 実行という要件にも反するため不採用）。

### 2. GitLab ホスト・プロジェクトID解決と URL エンコード
- **決定**: `git remote get-url origin` から HTTPS (`https://host/group/subgroup/repo.git`) および SSH (`git@host:group/subgroup/repo.git`, `ssh://git@host:port/group/repo.git`) をパースし、末尾 `.git` を除去したプロジェクトパスを `urllib.parse.quote(path, safe="")` でエンコードして `/api/v4/projects/{id}/merge_requests?state=opened&per_page=50` を呼び出す。`GITLAB_URL` / `GITLAB_PROJECT_ID` が設定されている場合はそちらを優先する。
- **理由**: GitLab はサブグループによる多階層パス（`a/b/c`）が一般的であり、`safe=""` による `/` の `%2F` エンコードが REST API v4 の仕様上必須であるため。また社内セルフホスト環境や複数リモート構成でも環境変数で確実に上書きできる。

### 3. API ルーティングとバックエンドモジュール分割
- **決定**:
  - `viewer_backend/parser.py`: Git Trailers (`Issue`, `Task`, `Why`, `What`, `Executed-Command`, `Verification`)・OpenSpec ID・変更種別分類。
  - `viewer_backend/gitlab_service.py`: リモート URL 解析、GitLab REST API v4 呼び出し、フォールバック生成。
  - `viewer_backend/git_service.py`: `git` サブプロセス実行、ref/SHA バリデーション、`gitlab_service` を呼び出す `list_mrs()`。
  - `server.py`: `GET /api/repo-info`, `GET /api/mrs`, `GET /api/commits`, `GET /api/commits/{sha}/diff` および `static/` 配信。
- **理由**: 責務を明確に分離し、各モジュール単位の高速な単体テストと 1サブタスク＝1コミットの実装粒度を両立するため。

### 4. フロントエンド構成と Diff2Html 同梱
- **決定**: `static/vendor/diff2html/` に `diff2html.min.css` と `diff2html-ui.min.js` を同梱し、Vanilla JS (ES Modules) + CSS で 3ペイン UI を構築する。確認済み状態は `localStorage` の `gitlab-mr-viewer:reviewed-commits` キーに保存する。
- **理由**: 外部 CDN 依存をなくし、閉域網・オフライン環境でも即座にシンタックスハイライト付き Split/Unified Diff を描画できるようにするため。

### 5. セキュリティ設計（コマンド・トークン保護）
- **決定**: `git` 実行はすべて `shell=False` の引数配列とし、ref は許可文字正規表現かつ `-` 始まり禁止、SHA は 4〜40 桁の16進数に限定する。`GITLAB_TOKEN` / `GITLAB_PRIVATE_TOKEN` は `PRIVATE-TOKEN` ヘッダーのみに設定し、例外メッセージ・フォールバック理由・標準出力には一切含めない。

## Risks / Trade-offs

- **[社内セルフホスト GitLab の自己署名証明書による SSL エラー]** → `urllib.request` が証明書検証エラーで失敗した場合はタイムアウト・エラー時と同様にローカルブランチ比較へ安全にフォールバックし、README に `SSL_CERT_FILE` 設定またはフォールバック利用について補足する。
- **[API 応答遅延による初期表示の待ち時間]** → API リクエストのタイムアウトを 5 秒に設定し、フロントエンド側では `/api/repo-info` と `/api/commits` をブロックせずに `/api/mrs` を独立して読み込むことで初期表示速度を維持する。
- **[MR のターゲット/ソースブランチがローカルに fetch されていない]** → ローカル `git log` で `base..head` が解決できない場合は HTTP 400 のエラーメッセージを UI 上部バナーに表示し、ユーザーに `git fetch` を促す。
