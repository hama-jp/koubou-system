#!/bin/bash
# LMStudio接続確認スクリプト

LMSTUDIO_HOST="192.168.11.29"
LMSTUDIO_PORT="1234"
LMSTUDIO_ENDPOINT="http://${LMSTUDIO_HOST}:${LMSTUDIO_PORT}/v1"
MODEL_ID="gpt-oss-20b@f16"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "LMStudio 接続チェック"
echo "========================================="
echo ""
echo "ホスト: $LMSTUDIO_HOST"
echo "ポート: $LMSTUDIO_PORT"
echo "モデル: $MODEL_ID"
echo ""

# ネットワーク接続確認
echo -n "1. ネットワーク接続確認... "
if ping -c 1 -W 2 $LMSTUDIO_HOST > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}失敗${NC}"
    echo "   → $LMSTUDIO_HOST に到達できません"
    exit 1
fi

# ポート接続確認
echo -n "2. ポート接続確認... "
if nc -z -w 2 $LMSTUDIO_HOST $LMSTUDIO_PORT 2>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}失敗${NC}"
    echo "   → ポート $LMSTUDIO_PORT が開いていません"
    exit 1
fi

# API接続確認
echo -n "3. API接続確認... "
RESPONSE=$(curl -s -w "\n%{http_code}" "${LMSTUDIO_ENDPOINT}/models" 2>/dev/null)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}OK${NC}"
    
    # モデル確認
    echo -n "4. モデル確認... "
    if echo "$BODY" | grep -q "$MODEL_ID"; then
        echo -e "${GREEN}OK${NC}"
        echo ""
        echo -e "${GREEN}✓ LMStudioは正常に動作しています${NC}"
        echo ""
        
        # 利用可能なモデル表示
        echo "利用可能なモデル:"
        echo "$BODY" | jq -r '.data[].id' 2>/dev/null || echo "$BODY"
    else
        echo -e "${YELLOW}警告${NC}"
        echo "   → モデル $MODEL_ID が見つかりません"
        echo ""
        echo "利用可能なモデル:"
        echo "$BODY" | jq -r '.data[].id' 2>/dev/null || echo "$BODY"
    fi
else
    echo -e "${RED}失敗${NC}"
    echo "   → HTTPステータス: $HTTP_CODE"
    echo "   → レスポンス: $BODY"
    exit 1
fi

echo ""
echo "テスト完了"