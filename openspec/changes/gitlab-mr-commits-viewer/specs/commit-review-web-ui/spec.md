# Spec Delta

## Purpose

完全ゼロ依存の Python HTTP/API サーバー、3ペイン構成の高速コミットレビュー Web UI（MR選択・キーボードナビゲーション・確認済み永続化・Diff表示切替）、および GitLab トークン権限設定手順を含む README ドキュメントを提供する。

## ADDED Requirements

### Requirement: ゼロ依存ローカル HTTP/API サーバー
**USDM**: R03-01
システムは Python 3 標準ライブラリのみを用いて HTTP/API サーバーを起動し、リポジトリ・MR・コミット・差分を取得する JSON API と静的 Web UI アセットを提供しなければならない（SHALL）。

#### Scenario: [S03-01-01] CLI 引数と環境変数でサーバーを起動する
- **WHEN** `--repo`、`--port`、`--host` 引数または `REPO_PATH`、`PORT`、`HOST` 環境変数を指定して `server.py` を起動する
- **THEN** 指定されたリポジトリを対象に `ThreadingHTTPServer` が起動し、静的ファイルおよび `/api/*` エンドポイントに応答する

#### Scenario: [S03-01-02] JSON API エンドポイントを提供する
- **WHEN** `GET /api/repo-info`、`GET /api/mrs`、`GET /api/commits`、`GET /api/commits/{sha}/diff` にリクエストする
- **THEN** 各エンドポイントが `application/json; charset=utf-8` かつ `Cache-Control: no-store` で構造化 JSON を返却する

### Requirement: 3ペイン構成のコミットレビュー Web UI
**USDM**: R03-02
システムはヘッダー（MR/ブランチ選択）、左ペイン（コミット一覧・確認済み管理）、中央・右ペイン（サマリカード・Diff2Html ビューア）の 3ペイン構成 UI とキーボード操作を提供しなければならない（SHALL）。

#### Scenario: [S03-02-01] ヘッダーの MR 選択で Base/Head を切り替える
- **WHEN** ヘッダーの MR ドロップダウンからオープン MR を選択する
- **THEN** 該当 MR の `target_branch` が Base、`source_branch` が Head に設定され、コミット一覧が自動的に再読込される

#### Scenario: [S03-02-02] 左ペインにコミット一覧と確認済み進捗を表示・永続化する
- **WHEN** コミット一覧が読み込まれ、ユーザーが確認済みチェックボックスをトグルする
- **THEN** 各コミットに変更種別バッジと OpenSpec タスクIDが表示され、確認済み状態が `localStorage` に永続化されて進捗（`X / Y Reviewed`）が更新される

#### Scenario: [S03-02-03] キーボードショートカットでコミット移動と確認済み切替を行う
- **WHEN** 入力要素にフォーカスがない状態で `j` / `↓`、`k` / `↑`、または `r` キーを押下する
- **THEN** ページリロードなしで次コミット移動、前コミット移動、または選択中コミットの確認済み状態トグルが実行される

#### Scenario: [S03-02-04] サマリカードと Split/Unified・空白無視切替付き Diff を表示する
- **WHEN** コミットを選択し、Split/Unified ボタンや空白無視（`-w`）チェックボックスを切り替える
- **THEN** 上部に `Why`/`What`/`Task`/`Verification`/`Executed-Command` のサマリカードが表示され、下部にファイルナビゲーションと選択モードに応じた Diff2Html 差分が表示される

### Requirement: README における利用手順と GitLab トークン権限設定手順の提供
**USDM**: R03-03
システムは `README.md` に起動方法・ショートカット・Git Trailers 形式・テスト手順に加え、GitLab REST API 実行に必要なトークン権限の設定手順を明記しなければならない（SHALL）。

#### Scenario: [S03-03-01] 基本的な利用手順とテスト手順を記載する
- **WHEN** 利用者が `README.md` を参照する
- **THEN** 動作要件、起動コマンド、キーボードショートカット、Git Trailers 形式、ディレクトリ構成、および `unittest` 実行コマンドが確認できる

#### Scenario: [S03-03-02] GitLab トークンの発行手順・必要スコープ・環境変数設定を記載する
- **WHEN** 利用者が GitLab MR 連携を設定するために `README.md` を参照する
- **THEN** Personal Access Token / Project Access Token の作成手順、必要な最小権限スコープ（`read_api`）、`GITLAB_TOKEN` / `GITLAB_URL` / `GITLAB_PROJECT_ID` の設定例、および未設定時のフォールバック動作が確認できる
