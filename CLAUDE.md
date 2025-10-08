# CLAUDE.md

AI開発ガイド: CIPetteプロジェクトでの作業指針

## プロジェクト概要

**CIPette** - GitHub ActionsのCI/CDメトリクスを可視化するシンプルなダッシュボード

**目標**: 5分でCI/CDインサイトを取得

## コア機能

- GitHub Actionsデータ収集
- ヘルススコア計算（0-100点）
- データ品質評価（5段階）
- Webダッシュボード表示

## AI作業指針

### コード品質
- **必ずリンター実行**: `uv run ruff check cipette/ tests/ --fix`
- 型ヒントを一貫して使用
- PEP 8スタイルガイドラインに従う

### テスト実行
- `uv run pytest` でテスト実行

### コミット前の品質チェック
**必須手順**:
1. **Lintチェック**: `uv run ruff check .`
2. **コードフォーマット**: `uv run ruff format .`
3. **テスト実行**: `uv run pytest tests/ -v`
4. **再チェック**: `uv run ruff check .` と `uv run ruff format --check .`

**品質保証**:
- すべてのlintチェックが通過すること
- すべてのテストが通過すること
- コードフォーマットが統一されていること

**方針**: 動作するソフトウェアを素早くリリース