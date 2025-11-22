from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Print DB connection target (db, host, user, version)."

    def handle(self, *args, **kwargs):
        with connection.cursor() as cur:
            cur.execute("select current_database(), inet_server_addr()::text, current_user, version()")
            db, host, user, ver = cur.fetchone()
        self.stdout.write(self.style.SUCCESS("Connected OK"))
        self.stdout.write(f"DB: {db}")
        self.stdout.write(f"Host: {host}")
        self.stdout.write(f"User: {user}")
        self.stdout.write(ver.splitlines()[0])
