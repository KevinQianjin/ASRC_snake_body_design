#!/bin/bash
set -Eeuo pipefail
umask 077
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="KevinQianjin/ASRC_snake_body_design"
REMOTE="https://github.com/$REPO.git"
SHARED_RUNTIME="$HOME/Library/Application Support/CodeGitHubUploader"
RUNTIME="$SHARED_RUNTIME/projects/ASRC-kevin-snake-body-design"
UPLOAD_FOLDER="ASRC_kevin"
GH="$SHARED_RUNTIME/bin/gh"
export GH_CONFIG_DIR="$SHARED_RUNTIME/config"
export GIT_DIR="$RUNTIME/repository.git"
export GIT_WORK_TREE="$PROJECT_DIR"
PAUSE=1
LOCKED=0
TEMP_DIR=""

finish() {
    result=$?
    trap - EXIT
    if [ -n "$TEMP_DIR" ]; then
        rm -f -- "$TEMP_DIR/index" "$TEMP_DIR/index.lock" "$TEMP_DIR/source-index" "$TEMP_DIR/source-index.lock"
        rmdir "$TEMP_DIR" 2>/dev/null || true
    fi
    if [ "$LOCKED" = 1 ]; then
        rmdir "$RUNTIME/upload.lock" 2>/dev/null || true
    fi
    if [ "$result" != 0 ]; then
        printf '\n上傳未完成。請查看上方錯誤；本機修改仍然保留。\n'
    fi
    if [ "$PAUSE" = 1 ] && [ -t 0 ]; then
        printf '\n按 Enter 關閉視窗。'
        read -r _ || true
    fi
    exit "$result"
}
trap finish EXIT
fail() { printf '\n%s\n' "$1" >&2; exit 1; }

case "${1:-}" in
    --check) PAUSE=0 ;;
    --no-pause) PAUSE=0 ;;
    "") ;;
    *) fail '不支援的參數。可用 --check 檢查設定。' ;;
esac

cd -- "$PROJECT_DIR"
[ -x "$GH" ] || fail '缺少本機 GitHub 工具，請恢復本機 CodeGitHubUploader 工具資料夾。'
[ -d "$GIT_DIR" ] || fail '這個資料夾尚未完成 Git 初始化。'
[ "$(git rev-parse --show-toplevel)" = "$PROJECT_DIR" ] || fail 'Git 專案路徑不符。'
[ "$(git remote get-url origin)" = "$REMOTE" ] || fail '上傳目標已變更，請先檢查 origin。'
[ "$(git symbolic-ref --quiet --short HEAD)" = main ] || fail '目前不是 main 分支，請先檢查分支。'

if [ "${1:-}" = --check ]; then
    printf '程式資料夾：%s\n目標倉庫：%s\n' "$PROJECT_DIR" "$REPO"
    "$GH" --version | head -n 1
    printf '模式：單向上傳，不下載或刪除本機檔案。\n'
    printf 'GitHub 資料夾：%s/\n' "$UPLOAD_FOLDER"
    printf '\n本機設定檢查通過。此檢查不會提交或上傳。\n'
    exit 0
fi

mkdir -p "$RUNTIME"
if ! mkdir "$RUNTIME/upload.lock" 2>/dev/null; then
    fail '已有上傳工作正在執行。請先查看其他上傳視窗。'
fi
LOCKED=1

if ! "$GH" auth status --hostname github.com >/dev/null 2>&1; then
    printf '\n首次使用：請依提示在 GitHub 網頁登入及授權。\n'
    "$GH" auth login --hostname github.com --git-protocol https --web
fi
[ "$("$GH" api user --jq .login)" = KevinQianjin ] || fail '請使用 KevinQianjin 帳號登入 GitHub。'

visibility=$("$GH" repo view "$REPO" --json visibility --jq .visibility)
[ "$visibility" = PUBLIC ] || [ "$visibility" = PRIVATE ] || fail '無法確認目標倉庫，已停止上傳。'

if git rev-parse --quiet --verify MERGE_HEAD >/dev/null ||
   git rev-parse --quiet --verify CHERRY_PICK_HEAD >/dev/null ||
   [ -d "$GIT_DIR/rebase-merge" ] || [ -d "$GIT_DIR/rebase-apply" ] ||
   [ -n "$(git ls-files --unmerged)" ]; then
    fail '已有未完成的合併或衝突，請先處理後再上傳。'
fi

# Build the upload with an isolated index. Never check out, pull, merge,
# reset, or write remote file contents into the OneDrive source folder.
TEMP_DIR="$(mktemp -d "$RUNTIME/upload.XXXXXX")"
index_git() { GIT_INDEX_FILE="$TEMP_DIR/index" git "$@"; }
source_git() { GIT_INDEX_FILE="$TEMP_DIR/source-index" git "$@"; }
HELPER="!\"$GH\" auth git-credential"
remote_git() { git -c credential.helper= -c "credential.helper=$HELPER" "$@"; }
local_head="$(git rev-parse --verify HEAD 2>/dev/null || true)"
if [ -n "$local_head" ]; then
    git update-ref refs/uploader/previous-main "$local_head"
fi

for attempt in 1 2 3; do
    printf '\n正在讀取 GitHub 版本（不更動本機檔案）……\n'
    remote_git fetch --prune origin
    remote_head="$(git rev-parse --verify refs/remotes/origin/main 2>/dev/null || true)"
    parents=()
    remote_tree=""
    if [ -n "$remote_head" ]; then
        index_git read-tree "$remote_head"
        remote_tree="$(git rev-parse "$remote_head^{tree}")"
        parents+=(-p "$remote_head")
    else
        index_git read-tree --empty
    fi
    remote_subtree=""
    if [ -n "$remote_head" ]; then
        remote_subtree="$(git rev-parse --verify "$remote_head:$UPLOAD_FOLDER" 2>/dev/null || true)"
    fi
    if [ -n "$remote_subtree" ]; then
        [ "$(git cat-file -t "$remote_subtree")" = tree ] || fail 'GitHub 上的 ASRC_kevin 是檔案而非資料夾，請先處理名稱衝突。'
        source_git read-tree "$remote_subtree"
    else
        source_git read-tree --empty
    fi
    preserve_history=0
    if [ -n "$local_head" ]; then
        if [ -z "$remote_head" ] || ! git merge-base --is-ancestor "$local_head" "$remote_head"; then
            parents+=(-p "$local_head")
            preserve_history=1
        fi
    fi

    # Overlay existing local files. Missing files on either side do not
    # delete files on the other side. Local contents win for matching paths.
    source_git add --ignore-removal -- .
    source_tree="$(source_git write-tree)"
    # Replace just the ASRC_kevin subtree in a temporary index. Keep every other
    # repository path unchanged. No operation writes remote files locally.
    index_git ls-files -z -- "$UPLOAD_FOLDER/" | index_git update-index --force-remove -z --stdin
    index_git read-tree --prefix="$UPLOAD_FOLDER/" "$source_tree"
    upload_tree="$(index_git write-tree)"
    if [ -n "$remote_head" ] && [ "$upload_tree" = "$remote_tree" ] && [ "$preserve_history" = 0 ]; then
        upload_commit="$remote_head"
    else
        upload_commit="$(git commit-tree "$upload_tree" "${parents[@]}" -m "Upload ASRC_kevin folder $(TZ=Asia/Hong_Kong date '+%Y-%m-%d %H:%M:%S %Z')")"
    fi
    git update-ref refs/uploader/pending "$upload_commit"
    printf '\n正在上傳 GitHub……\n'
    if remote_git push origin "$upload_commit:refs/heads/main"; then
        git update-ref refs/heads/main "$upload_commit" "$local_head" ||
            fail '上傳成功，但本機 Git 分支同時被其他程式修改；本機檔案未被更動。'
        git update-ref refs/remotes/origin/main "$upload_commit"
        git branch --set-upstream-to=origin/main main >/dev/null
        # Track the repository commit only; project files are always read-only.
        printf '\n上傳成功：https://github.com/%s/tree/main/%s\n' "$REPO" "$UPLOAD_FOLDER"
        printf '本機檔案已保留；遠端刪除不會同步到本機。\n'
        exit 0
    fi
    if [ "$attempt" -lt 3 ]; then
        printf '\n推送未成功，重新取得遠端更新後重試（%s/3）。\n' "$((attempt + 1))"
    fi
done
fail '重試後仍無法上傳；請檢查網路或遠端權限。本機提交已保留。'
