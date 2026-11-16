# Proposal

## Why

OpenSpec のように「1サブタスク＝1コミット」で積み上げた Git 履歴や GitLab Merge Request (MR) をレビューする際、GitLab の Web UI や通常の `git log` ではコミット単位の目的（Why / What）、OpenSpec タスクID、実行コマンド（Git Trailers）と差分を素早く切り替えながら俯瞰することが難しい。`github-pull-request-commits-viewer` と同じコンセプトのもと、GitLab REST API 連携に対応したローカル実行・完全ゼロ依存のコミット単位レビュービューアを構築し、あわせて API 利用に必要な GitLab トークン権限の設定手順を整備する。

## What Changes

- Python 3 標準ライブラリのみで構成されるゼロ依存 HTTP / API サーバー（`server.py`）およびバックエンドモジュール（`viewer_backend/`）を新規構築する。
- コミットメッセージ本文と Git Trailers（`Why`, `What`, `Issue`, `Task`, `Verification`, `Executed-Command`）を抽出し、変更種別（`command` / `test` / `manual`）と OpenSpec 仕様IDを自動判定するパーサーを実装する。
- `git` サブプロセスによるリポジトリ情報・ブランチ一覧・時系列コミット一覧・ファイル別統計・Unified Diff 取得機能を実装する（シェルインジェクションおよびオプションインジェクション対策を含む）。
- `gh` CLI の代わりに GitLab REST API v4（`urllib.request` と `PRIVATE-TOKEN` ヘッダー）を用いてオープン MR 一覧を取得し、未認証・APIエラー・オフライン時はローカルブランチ比較へ自動フォールバックする連携機能を実装する。
- ビルドレス Vanilla JS (ES Modules) + CSS + 同梱 Diff2Html による 3ペイン高速レビュー UI（`static/`）を実装する（MR / Base / Head 選択、`j`/`k`/`r` ショートカット、`localStorage` での確認済み管理、Split / Unified・空白無視切替）。
- `README.md` にアプリケーションの使い方に加え、GitLab REST API 実行に必要な Personal Access Token / Project Access Token の権限（`read_api` スコープ）および環境変数設定手順を記載する。

## Capabilities

### New Capabilities
- `git-commit-inspection`: ローカル Git リポジトリのメタデータ・ブランチ取得、`base..head` のコミット一覧と Git Trailers / OpenSpec ID 解析、およびコミット単位の Unified Diff / 変更統計取得。
- `gitlab-mr-integration`: ローカルリポジトリの `origin` リモートや環境変数からの GitLab ホスト・プロジェクト解決、GitLab REST API v4 によるオープン MR 一覧取得、および失敗時のローカルブランチ比較フォールバック。
- `commit-review-web-ui`: ゼロ依存ローカル HTTP/API サーバー、3ペイン構成のコミットレビュー Web UI（ショートカット操作・確認済み永続化・Diff 表示切替）、および `README.md` でのトークン権限設定ガイド提供。

### Modified Capabilities
<!-- 該当なし（新規プロジェクト構築のため） -->

## Impact

- 新規作成ファイル: `server.py`, `viewer_backend/__init__.py`, `viewer_backend/parser.py`, `viewer_backend/git_service.py`, `viewer_backend/gitlab_service.py`（または統合サービス）, `static/index.html`, `static/style.css`, `static/app.js`, `static/vendor/diff2html/*`, `tests/*`, `README.md`
- 外部システム連携: GitLab REST API v4（`/api/v4/projects/:id/merge_requests`）、ローカル `git` CLI
- 依存関係: ランタイム外部パッケージ依存なし（Python 3.8+ 標準ライブラリおよび同梱済み Diff2Html アセットのみ）
