from starter_weppy import db, auth
from starter_weppy.models.user import User


def setup_admin():
    from fixtures import TEST_ADMIN
    db._adapter.reconnect()
    admins = auth.id_group("admin") if auth.id_group("admin") else auth.add_group("admin")
    print("Admin group id: '{}'".format(admins))
    db._adapter.reconnect()
    admin = db.User.validate_and_insert(
            email=TEST_ADMIN.email,
            first_name=TEST_ADMIN.first_name,
            last_name=TEST_ADMIN.last_name,
            password=TEST_ADMIN.password
    )
    db.commit()
    db._adapter.reconnect()
    auth.add_membership(admins, admin.id)
    print("Admin created: \n{}".format(admin.as_dict()))
    db.commit()
    return admin


def remove_admin():
    from fixtures import TEST_ADMIN
    db._adapter.reconnect()
    print("\nRemoving test admin.")
    dev_admin = db(User.email == TEST_ADMIN.email).select()
    print("Admin: {}\n".format(dev_admin.as_dict()))
    db(User.email == TEST_ADMIN.email).delete()
    print("Test admin successfully deleted.")
    db.commit()


def setup_user():
    from fixtures import TEST_USER
    db._adapter.reconnect()
    user = db.User.validate_and_insert(
            email=TEST_USER.email,
            first_name=TEST_USER.first_name,
            last_name=TEST_USER.last_name,
            password=TEST_USER.password
    )
    db.commit()
    return user


def remove_user():
    from fixtures import TEST_USER
    db._adapter.reconnect()
    print("\nRemoving test user.")
    dev_user = db(User.email == TEST_USER.email).select()
    print("Admin: {}\n".format(dev_user.as_dict()))
    db(User.email == TEST_USER.email).delete()
    print("Test user successfully deleted.")
    db.commit()
