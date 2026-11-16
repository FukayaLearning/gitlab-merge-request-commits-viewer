# Tasks

<!-- ============================================================
  タスク分解・実装（apply-change）・アーカイブ（archive-change）ルール
  1. 1サブタスク（チェックボックス1項目）＝ 1コミット（変更ファイル1〜5個程度、単独でビルド・既存テストが通る Green State）
  2. 機械的変更（フォーマッタ、Linter自動修正、マイグレーション生成、sed一括置換、パッケージ追加等）は手動のロジック変更とは別の独立したサブタスク（＝別コミット）に切り出すこと
  3. apply-change 実行時は、チェックボックス1項目の遂行都度 tasks.md の [x] 更新を含めて以下の規約で即座にコミットすること:
     <type>(<scope>): <サブタスクの要約>

     Why: <なぜこの変更が必要か（目的・背景）>
     What: <何を変更したか>

     Issue: #<Issue番号>
     Task: <サブタスクの識別子または名称>
     Verification: <ビルド・テスト成功を確認したコマンド>
     Executed-Command: <機械的変更の場合のみ、実行したコマンド全文を記載（手動変更時は "manual"）>
  4. すべてのチェックボックス項目の実装・コミットが完了したら、最後にプロジェクト全体のテストを実行すること
============================================================ -->

## 1. バックエンド基盤・Git Trailers パーサー

- [x] 1.1 [S01-02-02, S01-02-03] `viewer_backend/__init__.py`、`viewer_backend/parser.py`（Git Trailers 抽出・OpenSpec 仕様ID抽出・変更種別判定）および `tests/test_parser.py` を実装する（検証: `python3 -m unittest tests/test_parser.py -v`）

## 2. GitLab REST API 連携サービス

- [x] 2.1 [S02-01-01, S02-01-02] `viewer_backend/gitlab_service.py` に `origin` リモート URL（HTTPS/SSH・サブグループ対応）からの GitLab ベース URL・プロジェクトパス抽出と環境変数上書きロジックを実装し、`tests/test_gitlab_service.py` で検証する（検証: `python3 -m unittest tests/test_gitlab_service.py -v`）
- [x] 2.2 [S02-02-01, S02-02-02, S02-03-01, S04-02] `viewer_backend/gitlab_service.py` に `urllib.request` を用いた GitLab REST API v4 オープン MR 一覧取得（`PRIVATE-TOKEN` ヘッダー対応・トークン非露出・自動フォールバック）を実装し、`tests/test_gitlab_service.py` に HTTP モックテストを追加する（検証: `python3 -m unittest tests/test_gitlab_service.py -v`）

## 3. Git リポジトリ検査サービスと HTTP/API サーバー

- [x] 3.1 [S01-01-01, S01-01-02, S04-01] `viewer_backend/git_service.py` にリポジトリ検証、`get_repo_info()`、および `validate_git_ref` / `validate_commit_sha` バリデーションを実装し、`tests/test_git_service.py` を追加する（検証: `python3 -m unittest tests/test_git_service.py -v`）
- [x] 3.2 [S01-02-01, S01-03-01, S01-03-02] `viewer_backend/git_service.py` に `get_commits()`、`get_commit_diff()`（`-w` 対応）、および `gitlab_service` 連携の `list_mrs()` を実装し、`tests/test_git_service.py` にテストを追加する（検証: `python3 -m unittest tests/test_git_service.py -v`）
- [x] 3.3 [S03-01-01, S03-01-02] `server.py` にゼロ依存 `ThreadingHTTPServer`（`/api/repo-info`, `/api/mrs`, `/api/commits`, `/api/commits/{sha}/diff`, 静的ファイル配信, CLI引数・環境変数対応）と `tests/test_server.py` を実装する（検証: `python3 -m unittest tests/test_server.py -v`）

## 4. フロントエンドアセット・3ペインレビュー Web UI

- [x] 4.1 [S03-02-04] （機械的変更）`static/vendor/diff2html/` に Diff2Html のローカルアセット（`diff2html.min.css`, `diff2html-ui.min.js`）を配置する（検証: `ls -la static/vendor/diff2html/` および `python3 -m unittest discover -s tests -v`）
- [x] 4.2 [S03-02-01, S03-02-02, S03-02-03, S03-02-04] `static/index.html`、`static/style.css`、`static/app.js` に 3ペイン構成レビュー UI（MR/ブランチ選択、コミット一覧・バッジ、`j`/`k`/`r` ショートカット、`localStorage` 永続化、サマリカード、Split/Unified・空白無視切替）を実装し、`tests/test_server.py` に静的アセット配信テストを追加する（検証: `python3 -m unittest discover -s tests -v`）

## 5. ドキュメント・トークン権限設定手順の整備

- [ ] 5.1 [S03-03-01, S03-03-02] `README.md` にプロジェクト概要、動作要件、起動方法、キーボードショートカット、Git Trailers 形式、テスト手順、および GitLab Personal/Project Access Token の発行手順・最小権限スコープ（`read_api`）・環境変数設定手順・フォールバック仕様を記載する（検証: `openspec validate gitlab-mr-commits-viewer --strict`）

## Workflow follow-up

- `apply-change` で全サブタスクの実装・個別コミット完了後、プロジェクト全体のテストスイート（`python3 -m unittest discover -s tests -v`）を実行してすべてパスすることを確認する。
- `archive-change` 実行時、完了して閉じるタスク（`- [x]`）に対応する `usdm.md` 内の各仕様（`[Sxx-yy-zz]`）について、要件のレビュー・実装・テストの完了状態に応じたUSDM仕様ラベルのチェック（`□□□` → `■□□` レビュー済み / `■■□` 実装済み / `■■■` テスト済み）を入れて `usdm.md` を更新・コミットしてからアーカイブする。
