"""
Web 登录态生成 CLI

用法示例:
    python -m app.cli.storage_state generate --project-identifier PRJ-1234 --env-id <uuid> --username admin --password secret
    python -m app.cli.storage_state status --project-identifier PRJ-1234 --job-id <uuid>
"""

import argparse
import asyncio
import getpass
import json
import sys
from uuid import UUID

from app.config.database import async_session_factory
from app.schemas.storage_state import LoginSelectors
from app.services.storage_state_service import StorageStateService


async def _cmd_generate(args: argparse.Namespace) -> None:
    password = args.password
    if not password:
        password = getpass.getpass("请输入登录密码: ")
    if not password:
        print("错误：密码不能为空", file=sys.stderr)
        sys.exit(1)

    selectors = None
    if args.login_url:
        selectors = LoginSelectors(
            login_url=args.login_url,
            username_selector=args.username_selector,
            password_selector=args.password_selector,
            submit_selector=args.submit_selector,
            success_selector=args.success_selector,
        )

    env_id = UUID(args.env_id) if args.env_id else None

    async with async_session_factory() as session:
        service = StorageStateService(session)
        info = await service.generate_and_wait(
            project_identifier=args.project_identifier,
            env_id=env_id,
            username=args.username,
            password=password,
            selectors=selectors,
            headless=args.headless,
            save_attachment=args.save_attachment,
        )

    output = json.dumps(info.model_dump(mode="json"), indent=2, ensure_ascii=False)
    try:
        print(output)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    if info.status != "completed":
        sys.exit(1)


async def _cmd_status(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        service = StorageStateService(session)
        info = await service.get_job(
            project_identifier=args.project_identifier,
            job_id=UUID(args.job_id),
        )
    output = json.dumps(info.model_dump(mode="json"), indent=2, ensure_ascii=False)
    try:
        print(output)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Web 登录态 storageState 生成工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="执行表单登录并生成 storageState.json")
    gen.add_argument("--project-identifier", required=True, help="项目标识符")
    gen.add_argument("--env-id", default=None, help="环境配置 ID（省略则使用默认环境）")
    gen.add_argument("--username", default=None, help="登录用户名；省略则从环境配置读取")
    gen.add_argument("--password", default=None, help="登录密码（不推荐命令行明文传入）")
    gen.add_argument("--login-url", default=None, help="登录页 URL")
    gen.add_argument(
        "--username-selector", default="input[name='username']", help="用户名输入框 CSS 选择器"
    )
    gen.add_argument(
        "--password-selector", default="input[name='password']", help="密码输入框 CSS 选择器"
    )
    gen.add_argument(
        "--submit-selector", default="button[type='submit']", help="提交按钮 CSS 选择器"
    )
    gen.add_argument(
        "--success-selector", default=".dashboard", help="登录成功标识元素 CSS 选择器"
    )
    gen.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头浏览器（默认）",
    )
    gen.add_argument(
        "--no-headless",
        action="store_true",
        help="弹出真实浏览器窗口",
    )
    gen.add_argument(
        "--save-attachment",
        action="store_true",
        default=True,
        help="将结果归档到 MinIO（默认）",
    )
    gen.add_argument(
        "--no-save-attachment",
        action="store_true",
        help="不归档到 MinIO",
    )

    status = subparsers.add_parser("status", help="查询生成任务状态")
    status.add_argument("--project-identifier", required=True, help="项目标识符")
    status.add_argument("--job-id", required=True, help="任务 ID")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        if args.no_headless:
            args.headless = False
        if args.no_save_attachment:
            args.save_attachment = False
        asyncio.run(_cmd_generate(args))
    elif args.command == "status":
        asyncio.run(_cmd_status(args))


if __name__ == "__main__":
    main()
