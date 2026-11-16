# Spec Delta

## Purpose

ローカル Git リポジトリの基本情報・ブランチ一覧の取得、`base..head` 範囲のコミットログおよび Git Trailers / OpenSpec 仕様IDの解析、ならびにコミット単位の Unified Diff と変更統計の安全な取得を提供する。

## ADDED Requirements

### Requirement: ローカルリポジトリ情報とブランチ一覧の取得
**USDM**: R01-01
システムは指定されたローカルパスが有効な Git リポジトリであることを検証し、リポジトリ名、パス、現在のブランチ、全ブランチ一覧、および既定のベースブランチ候補を返却しなければならない（SHALL）。

#### Scenario: [S01-01-01] 有効なリポジトリからメタデータとブランチ一覧を取得する
- **WHEN** 有効な Git リポジトリパスに対してリポジトリ情報取得を実行する
- **THEN** リポジトリ名、絶対パス、現在ブランチ、重複のないブランチ一覧、および優先順位（`main`, `master`, `develop`, `origin/main`, `origin/master`）に従った `default_base` が返却される

#### Scenario: [S01-01-02] 無効なリポジトリパスに対してエラーを返す
- **WHEN** 存在しないディレクトリまたは Git 管理外のディレクトリに対してリポジトリ情報取得を実行する
- **THEN** `GitRepositoryError` が送出され、API 経由の場合は HTTP 400 とエラーメッセージが返却される

### Requirement: コミット一覧取得と Git Trailers・OpenSpec ID 解析
**USDM**: R01-02
システムは `base..head` 範囲のコミットを時系列順（古い順）に取得し、コミット本文から Git Trailers と OpenSpec 仕様IDを抽出し、変更種別を分類しなければならない（SHALL）。

#### Scenario: [S01-02-01] 時系列順のコミット一覧を取得する
- **WHEN** 有効な `base` と `head` を指定してコミット一覧取得を実行する
- **THEN** `git log --reverse` により古い順で、SHA、短縮SHA、件名、本文、作成者、ISO 8601 日時を含むコミット配列が返却される

#### Scenario: [S01-02-02] Git Trailers と OpenSpec 仕様IDを抽出する
- **WHEN** `Issue`, `Task`, `Why`, `What`, `Executed-Command`, `Verification` の各トレーラーや `S01-02-03` 形式の仕様IDを含むコミットを解析する
- **THEN** 大文字・小文字を区別せずに各トレーラー値が抽出され、重複のない出現順の `task_ids` 配列が生成される

#### Scenario: [S01-02-03] コミットの変更種別を分類する
- **WHEN** `Executed-Command` が `"manual"` 以外の値を持つコミット、件名が `test:` で始まるコミット、または通常の実装コミットを解析する
- **THEN** それぞれ `change_type` が `command`、`test`、`manual` として分類される

### Requirement: コミット単位の変更統計と Unified Diff の取得
**USDM**: R01-03
システムは指定されたコミット SHA について変更ファイルごとの統計情報と Unified Diff 本文を取得し、空白無視オプションに対応しなければならない（SHALL）。

#### Scenario: [S01-03-01] コミットの変更ファイル統計と Diff を取得する
- **WHEN** 有効なコミット SHA を指定して差分取得を実行する
- **THEN** 各変更ファイルのパス、ステータスコード、追加行数、削除行数、バイナリ判定フラグ、および Unified Diff 文字列が返却される

#### Scenario: [S01-03-02] 空白無視オプション付きで Diff を取得する
- **WHEN** `ignore_whitespace=true` を指定して差分取得を実行する
- **THEN** `git show -w` を用いて空白文字のみの変更を除外した Unified Diff が返却される

### Requirement: 外部 git コマンド実行時のインジェクション防止
**USDM**: R04
システムは `git` サブプロセスをシェルを介さない引数配列形式で実行し、入力される Git ref および SHA を厳格に検証しなければならない（SHALL）。

#### Scenario: [S04-01] 不正な Git ref や SHA によるオプションインジェクションを拒否する
- **WHEN** 先頭が `-` で始まる ref（例: `--exec=evil`）や許可文字以外の文字を含む SHA が指定される
- **THEN** `git` コマンドを実行する前にバリデーションエラー（`ValueError` / HTTP 400）で拒否される
