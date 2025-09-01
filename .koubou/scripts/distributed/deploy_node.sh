#!/bin/bash

# 分散ワーカーノードデプロイメントスクリプト

set -e

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Koubou Distributed Worker Node Deployment${NC}"
echo "================================================"

# デフォルト値
NODE_TYPE="worker"
NODE_ID=""
LOCATION="local"
MASTER_HOST="localhost"
QUEUE_TYPE="local"
MAX_WORKERS=2
CAPABILITIES="general"
LLM_MODEL="gemma2:2b"
GPU=false
ENV="development"

# ヘルプ表示
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --type TYPE          Node type: master or worker (default: worker)
    --node-id ID         Node identifier (auto-generated if not specified)
    --location LOC       Node location (default: local)
    --master HOST        Master node host (default: localhost)
    --queue TYPE         Queue type: local, redis, rabbitmq (default: local)
    --max-workers N      Maximum workers (default: 2)
    --capabilities CAPS  Space-separated capabilities (default: general)
    --llm-model MODEL    LLM model (default: gemma2:2b)
    --gpu               Enable GPU support
    --env ENV           Environment: development, staging, production (default: development)
    --docker            Deploy using Docker
    --kubernetes        Deploy using Kubernetes
    --help              Show this help message

Examples:
    # Deploy local development worker
    $0 --type worker --node-id dev-01

    # Deploy production master node
    $0 --type master --env production --queue redis

    # Deploy GPU-enabled code generation node
    $0 --type worker --capabilities "code heavy_computation" --gpu --llm-model gpt-oss:20b

    # Deploy using Docker
    $0 --type worker --docker --node-id docker-worker-01

EOF
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            NODE_TYPE="$2"
            shift 2
            ;;
        --node-id)
            NODE_ID="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        --master)
            MASTER_HOST="$2"
            shift 2
            ;;
        --queue)
            QUEUE_TYPE="$2"
            shift 2
            ;;
        --max-workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        --capabilities)
            CAPABILITIES="$2"
            shift 2
            ;;
        --llm-model)
            LLM_MODEL="$2"
            shift 2
            ;;
        --gpu)
            GPU=true
            shift
            ;;
        --env)
            ENV="$2"
            shift 2
            ;;
        --docker)
            DEPLOY_DOCKER=true
            shift
            ;;
        --kubernetes)
            DEPLOY_K8S=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# ノードIDの自動生成
if [ -z "$NODE_ID" ]; then
    NODE_ID="${NODE_TYPE}-$(hostname)-$(date +%s | tail -c 5)"
fi

# 環境変数設定
setup_environment() {
    echo -e "${YELLOW}Setting up environment...${NC}"
    
    # 環境別設定
    case $ENV in
        development)
            export MQ_HOST="localhost"
            export MQ_PORT="6379"
            export LOG_LEVEL="DEBUG"
            ;;
        staging)
            export MQ_HOST="redis.staging.koubou.internal"
            export MQ_PORT="6379"
            export LOG_LEVEL="INFO"
            ;;
        production)
            export MQ_HOST="redis.prod.koubou.internal"
            export MQ_PORT="6379"
            export LOG_LEVEL="WARNING"
            ;;
    esac
    
    # LLM設定
    export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    export CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
}

# 依存関係チェック
check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"
    
    # Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Queue-specific checks
    case $QUEUE_TYPE in
        redis)
            if ! command -v redis-cli &> /dev/null; then
                echo -e "${YELLOW}Installing Redis client...${NC}"
                pip install redis
            fi
            ;;
        rabbitmq)
            if ! python3 -c "import pika" &> /dev/null; then
                echo -e "${YELLOW}Installing RabbitMQ client...${NC}"
                pip install pika
            fi
            ;;
    esac
    
    # Ollama check (for workers)
    if [ "$NODE_TYPE" = "worker" ]; then
        if ! command -v ollama &> /dev/null; then
            echo -e "${YELLOW}Warning: Ollama not found. Installing...${NC}"
            curl -fsSL https://ollama.ai/install.sh | sh
        fi
        
        # モデルの確認とダウンロード
        if ! ollama list | grep -q "$LLM_MODEL"; then
            echo -e "${YELLOW}Pulling LLM model: $LLM_MODEL${NC}"
            ollama pull "$LLM_MODEL"
        fi
    fi
}

# Dockerデプロイメント
deploy_docker() {
    echo -e "${GREEN}Deploying with Docker...${NC}"
    
    # Dockerfileの生成
    cat > /tmp/Dockerfile.koubou << EOF
FROM python:3.9-slim

WORKDIR /app

# 依存関係インストール
RUN pip install flask flask-cors requests pyyaml psutil redis pika

# スクリプトコピー
COPY .koubou/scripts /app/scripts

# 環境変数
ENV NODE_ID=$NODE_ID
ENV NODE_TYPE=$NODE_TYPE
ENV QUEUE_TYPE=$QUEUE_TYPE
ENV MASTER_HOST=$MASTER_HOST

# 実行
CMD ["python", "/app/scripts/distributed/${NODE_TYPE}_node.py"]
EOF

    # Dockerイメージビルド
    docker build -f /tmp/Dockerfile.koubou -t koubou-${NODE_TYPE}:${NODE_ID} .
    
    # コンテナ起動
    docker run -d \
        --name koubou-${NODE_ID} \
        --network host \
        -e NODE_ID=$NODE_ID \
        -e LOCATION=$LOCATION \
        -e MAX_WORKERS=$MAX_WORKERS \
        -e CAPABILITIES="$CAPABILITIES" \
        -e LLM_MODEL=$LLM_MODEL \
        koubou-${NODE_TYPE}:${NODE_ID}
    
    echo -e "${GREEN}Docker container started: koubou-${NODE_ID}${NC}"
}

# Kubernetesデプロイメント
deploy_kubernetes() {
    echo -e "${GREEN}Deploying to Kubernetes...${NC}"
    
    # マニフェスト生成
    cat > /tmp/koubou-${NODE_ID}.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: koubou-${NODE_ID}
  labels:
    app: koubou
    node-type: ${NODE_TYPE}
    node-id: ${NODE_ID}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: koubou
      node-id: ${NODE_ID}
  template:
    metadata:
      labels:
        app: koubou
        node-type: ${NODE_TYPE}
        node-id: ${NODE_ID}
    spec:
      containers:
      - name: koubou-node
        image: koubou-${NODE_TYPE}:latest
        env:
        - name: NODE_ID
          value: "${NODE_ID}"
        - name: NODE_TYPE
          value: "${NODE_TYPE}"
        - name: LOCATION
          value: "${LOCATION}"
        - name: MASTER_HOST
          value: "${MASTER_HOST}"
        - name: QUEUE_TYPE
          value: "${QUEUE_TYPE}"
        - name: MAX_WORKERS
          value: "${MAX_WORKERS}"
        - name: CAPABILITIES
          value: "${CAPABILITIES}"
        - name: LLM_MODEL
          value: "${LLM_MODEL}"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "8Gi"
            cpu: "4"
EOF

    # GPU対応
    if [ "$GPU" = true ]; then
        cat >> /tmp/koubou-${NODE_ID}.yaml << EOF
            nvidia.com/gpu: 1
EOF
    fi

    # デプロイ
    kubectl apply -f /tmp/koubou-${NODE_ID}.yaml
    
    echo -e "${GREEN}Kubernetes deployment created: koubou-${NODE_ID}${NC}"
}

# ローカルデプロイメント
deploy_local() {
    echo -e "${GREEN}Deploying locally...${NC}"
    
    # スクリプトパス
    SCRIPT_DIR="$(dirname "$0")"
    
    if [ "$NODE_TYPE" = "master" ]; then
        # マスターノード起動
        python3 "$SCRIPT_DIR/master_node.py" \
            --node-id "$NODE_ID" \
            --location "$LOCATION" \
            --queue-type "$QUEUE_TYPE" \
            --routing "${ROUTING_STRATEGY:-load_balanced}" &
    else
        # ワーカーノード起動
        python3 "$SCRIPT_DIR/remote_worker_node.py" \
            --node-id "$NODE_ID" \
            --location "$LOCATION" \
            --master "$MASTER_HOST" \
            --queue-type "$QUEUE_TYPE" \
            --max-workers "$MAX_WORKERS" \
            --capabilities $CAPABILITIES \
            --llm-model "$LLM_MODEL" \
            $([ "$GPU" = true ] && echo "--gpu") &
    fi
    
    PID=$!
    echo $PID > /tmp/koubou-${NODE_ID}.pid
    
    echo -e "${GREEN}Node started with PID: $PID${NC}"
    echo -e "${GREEN}PID saved to: /tmp/koubou-${NODE_ID}.pid${NC}"
}

# ステータス確認
check_status() {
    echo -e "${YELLOW}Checking node status...${NC}"
    
    if [ -f /tmp/koubou-${NODE_ID}.pid ]; then
        PID=$(cat /tmp/koubou-${NODE_ID}.pid)
        if ps -p $PID > /dev/null; then
            echo -e "${GREEN}Node is running (PID: $PID)${NC}"
        else
            echo -e "${RED}Node is not running${NC}"
        fi
    else
        echo -e "${YELLOW}No PID file found${NC}"
    fi
    
    # Dockerステータス
    if [ "$DEPLOY_DOCKER" = true ]; then
        docker ps | grep koubou-${NODE_ID} || echo -e "${YELLOW}Docker container not found${NC}"
    fi
    
    # Kubernetesステータス
    if [ "$DEPLOY_K8S" = true ]; then
        kubectl get pods -l node-id=${NODE_ID}
    fi
}

# メイン処理
main() {
    echo -e "${GREEN}Deploying Koubou Node${NC}"
    echo "================================"
    echo "Node Type: $NODE_TYPE"
    echo "Node ID: $NODE_ID"
    echo "Location: $LOCATION"
    echo "Environment: $ENV"
    echo "Queue Type: $QUEUE_TYPE"
    
    if [ "$NODE_TYPE" = "worker" ]; then
        echo "Master Host: $MASTER_HOST"
        echo "Max Workers: $MAX_WORKERS"
        echo "Capabilities: $CAPABILITIES"
        echo "LLM Model: $LLM_MODEL"
        echo "GPU Enabled: $GPU"
    fi
    
    echo "================================"
    
    # 環境セットアップ
    setup_environment
    
    # 依存関係チェック
    check_dependencies
    
    # デプロイメント実行
    if [ "$DEPLOY_DOCKER" = true ]; then
        deploy_docker
    elif [ "$DEPLOY_K8S" = true ]; then
        deploy_kubernetes
    else
        deploy_local
    fi
    
    # ステータス確認
    sleep 3
    check_status
    
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
}

# 実行
main