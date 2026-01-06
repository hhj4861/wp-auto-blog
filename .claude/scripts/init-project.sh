#!/bin/bash
#
# init-project.sh - 신규 프로젝트에 venture-studio 에이전트/스킬/표준화문서 연동
#
# 사용법:
#   ./scripts/init-project.sh <project-name>
#   ./scripts/init-project.sh gonggu-match-next
#
# 설명:
#   ~/home/IdeaProjects/{project-name}/ 폴더에 다음 심볼릭 링크를 생성합니다:
#   - .claude/agents → venture-studio 에이전트
#   - .claude/standards → venture-studio 표준화 문서
#   - .claude/skills → venture-studio 스킬
#
#   이를 통해 해당 프로젝트에서 venture-studio의 모든 리소스를 사용할 수 있습니다.
#

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 경로 설정
VENTURE_STUDIO_PATH=~/home/IdeaProjects/venture-studio
PROJECTS_BASE_PATH=~/home/IdeaProjects

PROJECT_NAME=$1

# 사용법 출력
usage() {
    echo "Usage: $0 <project-name>"
    echo ""
    echo "Examples:"
    echo "  $0 my-new-project"
    echo "  $0 gonggu-match-next"
    echo ""
    echo "This script creates symlinks from the project's .claude/ to:"
    echo "  - agents/   → venture-studio agents (에이전트)"
    echo "  - standards/ → venture-studio standards (표준화 문서)"
    echo "  - skills/   → venture-studio skills (스킬)"
    exit 1
}

# 인자 확인
if [ -z "$PROJECT_NAME" ]; then
    echo -e "${RED}Error: Project name is required${NC}"
    usage
fi

PROJECT_PATH="$PROJECTS_BASE_PATH/$PROJECT_NAME"

# 프로젝트 폴더 존재 확인
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${YELLOW}Warning: $PROJECT_PATH does not exist${NC}"
    read -p "Create the folder? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$PROJECT_PATH"
        echo -e "${GREEN}Created: $PROJECT_PATH${NC}"
    else
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
fi

# venture-studio 폴더 존재 확인
if [ ! -d "$VENTURE_STUDIO_PATH/.claude" ]; then
    echo -e "${RED}Error: venture-studio .claude folder not found${NC}"
    echo "Expected: $VENTURE_STUDIO_PATH/.claude"
    exit 1
fi

# .claude 폴더 생성
mkdir -p "$PROJECT_PATH/.claude"

# 심볼릭 링크 생성 함수
create_symlink() {
    local SOURCE=$1
    local TARGET=$2
    local NAME=$3

    # 소스 존재 확인
    if [ ! -d "$SOURCE" ]; then
        echo -e "${YELLOW}Warning: $SOURCE does not exist, skipping $NAME${NC}"
        return
    fi

    # 기존 심볼릭 링크 확인
    if [ -L "$TARGET" ]; then
        echo -e "${YELLOW}Symlink $NAME already exists. Recreating...${NC}"
        rm "$TARGET"
    elif [ -d "$TARGET" ]; then
        echo -e "${RED}Error: $TARGET is a directory, not a symlink${NC}"
        echo "Please remove it manually if you want to create a symlink."
        return
    fi

    # 심볼릭 링크 생성
    ln -sf "$SOURCE" "$TARGET"

    if [ -L "$TARGET" ]; then
        echo -e "${GREEN}✓ $NAME symlink created${NC}"
    else
        echo -e "${RED}✗ Failed to create $NAME symlink${NC}"
    fi
}

echo ""
echo -e "${BLUE}Creating symlinks for project: $PROJECT_NAME${NC}"
echo ""

# agents 심볼릭 링크
create_symlink \
    "$VENTURE_STUDIO_PATH/.claude/agents" \
    "$PROJECT_PATH/.claude/agents" \
    "agents"

# standards 심볼릭 링크
create_symlink \
    "$VENTURE_STUDIO_PATH/.claude/standards" \
    "$PROJECT_PATH/.claude/standards" \
    "standards"

# skills 심볼릭 링크
create_symlink \
    "$VENTURE_STUDIO_PATH/.claude/skills" \
    "$PROJECT_PATH/.claude/skills" \
    "skills"

# 결과 출력
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Venture Studio integration complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Project: $PROJECT_NAME"
echo "Path:    $PROJECT_PATH"
echo ""
echo "Symlink details:"
ls -la "$PROJECT_PATH/.claude/"
echo ""
echo "Available agents:"
ls "$PROJECT_PATH/.claude/agents/" 2>/dev/null | head -5 || echo "  (none)"
echo ""
echo "Standards folders:"
ls "$PROJECT_PATH/.claude/standards/" 2>/dev/null | head -5 || echo "  (none)"
echo ""
echo -e "${GREEN}You can now use venture-studio resources in this project!${NC}"
echo ""
echo "Example usage:"
echo "  cd $PROJECT_PATH"
echo "  claude"
echo "  > \"프론트엔드 개발해줘\""
