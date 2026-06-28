安装及注意事项：
一、安装依赖
1、新建uv 环境（python 3.13），将当前目录下所有代码复制到项目目录下
2、安装后端依赖，打开终端界面，输入 uv sync
   注意：uv sync 会重新安装 .venv 中的 deepagents，但服务启动脚本会自动把 messages reducer 补丁写回，无需手动修改。
3、安装前端依赖并运行，打开终端界面，cd ui 进入ui目录，然后执行 npm install，然后执行npm run dev
4、编辑根目录下的 .env文件，修改相应的api key及相关服务器地址

启动后端服务：
注意：
如果使用 start_server_inmem.py 启动服务，必须将langgraph_api 随意命名一下，例如修改成 langgraph_api_1

如果使用 start_server_postgres.py 启动服务，按照如下进行操作：
0、安装依赖：uv sync
1、langgraph_api、langgraph_license、langgraph_runtime_postgres 这三个文件保持在当前目录下不动
2、将langgraph_source/checkpoint/postgres 复制到 .venv/lib/langgraph/checkpoint 目录下
3、将langgraph_source/store/postgres 复制到 .venv/lib/langgraph/store 目录下
4、openapi.json 要和langgraph_api在一起，不能删除
5、storage目录下是数据库创建脚本，默认不动
6、可以在langgraph.json文件中配置智能体
7、deepagents messages reducer 补丁已由 start_server_postgres.py / start_server_inmem.py 自动维护，启动时会自动检测并应用
8、根据自己的情况修改.env文件中的如下信息：
    DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
    REDIS_URI=YOUR_REDIS_URI
    DATABASE_URI=YOUR_DATABASE_URI

启动自定义的后端登录及注册系统的目录：直接运行 app/main.py
