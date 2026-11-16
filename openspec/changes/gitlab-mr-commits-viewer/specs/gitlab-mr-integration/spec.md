# Spec Delta

## Purpose

ローカル Git リポジトリの `origin` リモートおよび環境変数から GitLab ホストとプロジェクトを自動解決し、GitLab REST API v4 を用いたオープン Merge Request 一覧の取得と、API 利用不可時のローカルブランチ比較フォールバックを提供する。

## ADDED Requirements

### Requirement: GitLab ホストとプロジェクトパスの解決
**USDM**: R02-01
システムは `git remote get-url origin` から GitLab ベース URL とプロジェクトパス（サブグループ含む）を抽出し、環境変数 `GITLAB_URL` および `GITLAB_PROJECT_ID` が設定されている場合はそれらを優先しなければならない（SHALL）。

#### Scenario: [S02-01-01] HTTPS および SSH 形式の origin URL から GitLab 情報を抽出する
- **WHEN** `origin` リモート URL が `https://gitlab.example.com/group/subgroup/repo.git` または `git@gitlab.example.com:group/subgroup/repo.git` である
- **THEN** ベース URL `https://gitlab.example.com` とプロジェクトパス `group/subgroup/repo` が抽出される

#### Scenario: [S02-01-02] 環境変数による GitLab ホストとプロジェクトの上書きを優先する
- **WHEN** `GITLAB_URL` または `GITLAB_PROJECT_ID` 環境変数が設定されている
- **THEN** 自動抽出された値ではなく環境変数の値が API リクエスト先の構築に使用される

### Requirement: GitLab REST API v4 によるオープン Merge Request 一覧取得
**USDM**: R02-02
システムは Python 標準ライブラリの `urllib.request` を用いて GitLab REST API v4 の Merge Requests エンドポイントを呼び出し、オープン中の MR 一覧を正規化して返却しなければならない（SHALL）。

#### Scenario: [S02-02-01] オープン MR 一覧を取得して正規化する
- **WHEN** 有効な GitLab プロジェクトとネットワーク接続があり、`GET /api/v4/projects/{url_encoded_project}/merge_requests?state=opened&per_page=50` が成功する
- **THEN** 各 MR の `iid`（番号）、`title`、`source_branch`、`target_branch`、`web_url` を含む一覧が `fallback: false` で返却される

#### Scenario: [S02-02-02] トークン設定時に PRIVATE-TOKEN ヘッダーを付与する
- **WHEN** 環境変数 `GITLAB_TOKEN` または `GITLAB_PRIVATE_TOKEN` が設定されている
- **THEN** GitLab REST API への HTTP リクエストに `PRIVATE-TOKEN` ヘッダーが付与される

### Requirement: GitLab API 利用不可時のローカルブランチ比較フォールバック
**USDM**: R02-03
システムはリモート未設定、認証失敗、通信エラー、またはオープン MR が 0 件の場合にサーバーエラーとせず、ローカルブランチ比較へ自動フォールバックしなければならない（SHALL）。

#### Scenario: [S02-03-01] API 失敗時または MR 0 件時にフォールバックレスポンスを返す
- **WHEN** GitLab API が HTTP 401/403/404 を返す、ネットワークがタイムアウトする、またはオープン MR が 0 件である
- **THEN** 空の MR 一覧、`fallback: true`、簡潔な `reason`、および `default_base` / `default_head` が返却される

### Requirement: GitLab API トークンの機密保護
**USDM**: R04
システムは `GITLAB_TOKEN` および `GITLAB_PRIVATE_TOKEN` の値をログ、HTTP エラーレスポンス、およびフォールバック理由文字列に出力してはならない（MUST NOT）。

#### Scenario: [S04-02] API エラー時のレスポンスにトークン値を含めない
- **WHEN** `GITLAB_TOKEN` が設定された状態で GitLab API リクエストが認証エラーまたは通信エラーで失敗する
- **THEN** 返却される `reason` やエラーメッセージにトークン文字列は含まれない
