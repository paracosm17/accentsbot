IMPORTANT:
accentsbot PostgreSQL data is currently stored in external Docker volume:

22845ff40998408bc91ff1076a7709abb8b6410c9fb47a0773104c456948d341

It is mounted through docker-compose.override.yml as:
accents_pgdata_recovered -> /var/lib/postgresql/data

Do not delete this volume.
Do not run docker volume prune without checking this file.
Recovery dump:
/opt/backups/postgres/accentsbot/accentsbot-after-recovery-20260608-200540.sql.gz
