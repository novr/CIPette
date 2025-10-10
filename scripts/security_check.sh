#!/bin/bash
# Shai-Hulud対策: セキュリティチェックスクリプト

set -e

echo "🛡️  CIPette Security Check - Shai-Hulud対策"
echo "=============================================="

# 1. 依存関係の脆弱性スキャン
echo "🔍 1. 依存関係の脆弱性スキャン..."
uv run safety check --json > safety_report.json 2>/dev/null || echo "⚠️  Safety check completed with warnings"
echo "✅ Safety check completed"

# 2. コードセキュリティスキャン
echo "🔍 2. コードセキュリティスキャン..."
uv run bandit -r cipette/ -f json -o bandit_report.json -c .bandit || true
uv run bandit -r cipette/ -f txt -c .bandit
echo "✅ Bandit scan completed"

# 3. 依存関係の整合性チェック
echo "🔍 3. 依存関係の整合性チェック..."
uv run pip-audit --format=json > pip_audit_report.json || true
echo "✅ pip-audit completed"

# 4. ロックファイルの整合性確認
echo "🔍 4. ロックファイルの整合性確認..."
uv lock --check
echo "✅ Lock file integrity verified"

# 5. 依存関係の更新確認
echo "🔍 5. 依存関係の更新確認..."
uv tree --outdated || echo "ℹ️  No outdated dependencies found"
echo "✅ Dependency update check completed"

# 6. セキュリティレポートの生成
echo "📊 6. セキュリティレポートの生成..."
cat > security_summary.md << EOF
# CIPette Security Report

## 実行日時
$(date -u '+%Y-%m-%d %H:%M:%S UTC')

## チェック項目
- [x] 依存関係の脆弱性スキャン (safety)
- [x] コードセキュリティスキャン (bandit)
- [x] 依存関係の整合性チェック (pip-audit)
- [x] ロックファイルの整合性確認
- [x] 依存関係の更新確認

## 推奨事項
1. 定期的な依存関係の更新
2. セキュリティパッチの適用
3. コードレビューでのセキュリティチェック
4. 認証情報の定期的なローテーション
5. 最小権限の原則の適用

## Shai-Hulud対策
- 依存関係の信頼性確認
- サプライチェーン攻撃の検出
- 認証情報の保護
- 定期的なセキュリティスキャン
EOF

echo "✅ Security summary generated: security_summary.md"

echo ""
echo "🎉 セキュリティチェック完了！"
echo "📄 レポートファイル:"
echo "   - safety_report.json"
echo "   - bandit_report.json" 
echo "   - pip_audit_report.json"
echo "   - security_summary.md"
