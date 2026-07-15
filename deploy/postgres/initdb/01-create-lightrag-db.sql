-- LightRAG PGDocStatusStorage 专用数据库（仅在 postgres 数据卷首次初始化时执行）
SELECT 'CREATE DATABASE lightrag'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'lightrag')\gexec
