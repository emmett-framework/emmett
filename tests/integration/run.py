from contextlib import contextmanager
from argparse import ArgumentParser
from starter_weppy import app


@contextmanager
def run_in_dev():
    from dev_utils import remove_admin, remove_user
    try:
        yield
    finally:
        remove_admin()
        remove_user()


if __name__ == "__main__":
    arg_parser = ArgumentParser(description="StarterWeppy running utility.")
    arg_parser.add_argument('-d', '--dev', help="Setup add dev users and enable verbose logging",
                            action='store_true')
    arg_parser.add_argument('-t', '--test', help="Run test server (setup dev users but squelch logging and reloader",
                            action='store_true')
    args = arg_parser.parse_args()
    if args.dev or args.test:
        from dev_utils import setup_admin, setup_user
        TEST_ADMIN = setup_admin()
        TEST_USER = setup_user()
        print("Admin: {} \nUser: {}\n".format(TEST_ADMIN.as_dict(), TEST_USER.as_dict()))
        with run_in_dev():
            if args.dev:
                app.run()
            else:
                app.run(reloader=False)
    else:
        app.run(host="0.0.0.0", debug=False)
