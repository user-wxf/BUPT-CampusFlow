"""python -m app.create_admin admin；密码通过终端隐藏输入。"""
import argparse
import getpass
from sqlalchemy import select
from .database import Base, engine, SessionLocal, User
from .schemas import Credentials
from .security import hash_password


def main():
    parser = argparse.ArgumentParser(description='创建管理员（不覆盖已有账号）')
    parser.add_argument('username')
    args = parser.parse_args()
    password = getpass.getpass('管理员密码（至少8位）: ')
    if password != getpass.getpass('确认密码: '):
        raise SystemExit('两次密码不一致')
    data = Credentials(username=args.username, password=password)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == data.username)):
            raise SystemExit('用户名已存在，请使用其他名称')
        db.add(User(username=data.username, password_hash=hash_password(data.password), role='admin'))
        db.commit()
    print('管理员已创建')


if __name__ == '__main__':
    main()
