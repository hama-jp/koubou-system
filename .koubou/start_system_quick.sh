#!/bin/bash
# 🏭 工房システム クイック起動スクリプト（バックグラウンド実行専用）

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

KOUBOU_HOME="$(cd "$(dirname "$0")" && pwd)"

echo -e "${CYAN}🏭 工房システム クイック起動${NC}"
echo -e "${YELLOW}📝 バックグラウンドモードで起動します...${NC}"

# バックグラウンドモードで起動
"$KOUBOU_HOME/start_system.sh" --background

echo ""
echo -e "${GREEN}✅ 起動完了！${NC}"
echo ""
echo -e "${BLUE}📊 サービスURL:${NC}"
echo -e "  • Dashboard: ${GREEN}http://localhost:8080${NC}"
echo -e "  • MCP API: ${GREEN}http://localhost:8765${NC}"
echo -e "  • Worker Logs: ${GREEN}http://localhost:8768${NC}"
echo ""
echo -e "${YELLOW}停止コマンド: ${NC}.koubou/stop_system.sh"
echo ""