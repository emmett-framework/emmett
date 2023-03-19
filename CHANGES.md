Emmett changelog
================

Version 2.5
-----------

Released on March 19th 2023, codename Fermi

- Added official Python 3.11 support
- Removed support for legacy encryption stack
- Added RSGI protocol support
- Use Granian as default web server in place of uvicorn
- Added application modules groups
- Dropped Python 3.7 support

Version 2.4
-----------

Released on January 10th 2022, codename Edison

- Added official Python 3.10 support
- Added relative path support in templates
- Added support for spatial columns in ORM
- Added support for custom/multiple primary keys in ORM
- Added support for custom/multiple foreign keys in ORM
- Added support for custom and multiple primary keys relations in ORM
- Added `watch` parameter to ORM's `compute` decorator
- Added `save` method to ORM's rows and relevant callbacks
- Added `destroy` method to ORM's rows and relevant callbacks
- Added `refresh` method to ORM's rows
- Added `before_commit` and `after_commit` ORM callbacks
- Added changes tracking to ORM's rows
- Added support to call super `rowmethod` decorated methods in ORM models
- Added `migrations set` command to CLI
- Added `skip_callbacks` parameter to relevant methods in ORM
- ORM now automatically adds appropriate indexes for `unique` fields

Version 2.3
-----------

Released on August 12th 2021, codename Da Vinci

- Minor enhancements on request flow
- Added ORM support for PostgreSQL json/jsonb fields and operators
- Added `widget_radio` to `forms.FormStyle`
- Added `dict` values support for `in` validations
- Use optional `emmett-crypto` package for cryptographic functions
- Deprecated `security.secure_dumps` and `security.secure_loads` in favour of new crypto package
- Added `on_delete` option to `belongs_to` and `refers_to`
- Added `--dry-run` option to migrations `up` and `down` commands

Version 2.2
-----------

Released on March 11th 2021, codename Copernicus

- Slightly refactored request flow
- Added `App.command_group` decorator
- Added additional arguments acceptance in `AppModule`
- Added static paths customisation for `AppModule`
- Added `workers` options to `serve` command
- Changed default logging level to `info` in `serve` command
- Changed default `SameSite` policy for session cookies to `Lax`
- Added official Python 3.9 support

Version 2.1
-----------

Released on October 17th 2020, codename Bell

- Added type hints on all major interfaces
- Deprecated `App.run`
- Deprecated string signals in favour of `extensions.Signals`
- Removed `libs.sanitizer`
- Use `orjson` for JSON serialization
- Refactored request flow internals
- Added namespaces to templater
- Added `SameSite` support to session cookies
- Added HTTP/2 support
- Added `Request.push_promise`
- Added Python 3.9 support (beta)

Version 2.0
-----------

Released on May 3rd 2020, codename Archimedes

- Dropped Python 2 support, requiring Python 3.7 minimum version
- Changed package name to `emmett`
- Moved from WSGI to ASGI
- Moved to async syntax
- Moved `globals` module to `ctx`
- Added `output` optional param to `route` definition
- Introduced `develop` and `serve` commands in place of `run`
- Pipeline `open` and `close` flows are now handled concurrently
- Rewritten router, optimized request flow
- Introduced websockets support
- Added `after_loop` signal
- Decoupled templating engine
- Added `Request.files`
- Added `request_max_content_length` to `App.config`
- Added `request_body_timeout` to `App.config`
- Added async support in `cache` module
- Decoupled internationalization engine
- Added runtime migration utils in ORM
- Added `response_timeout` to `App.config`
- Use default `text/plain` Content-Type header in responses
- Added `namespace` to `Injector` class
- Added Python 3.8 support

Version 1.3
-----------

Released on October 29th 2018, codename Nunki

- Minor bugfixes
- Added proper support for 'big' id and reference fields to ORM
- Added `url_prefix` global routing paramater to `App`
- Allow to specify different `templates_encoding` for templates loading in
  application config
- Added `migrations_folder` variable to database configuration to support
  migrations with multiple databases
- Added support for Python 3.7
- Refactored `join` and `including` options handling in ORM
- Added `cast` method to ORM `Field`
- Added `cast` options to `has_many` decorator
- Optimized pipeline flow
- Optimized router match code


Version 1.2
-----------

Released on October 23rd 2017, codename Merak

- Several bugfixes
- Rewritten templates parsing and generation logic
- Rewritten ORM connection pooling
- Added support for advanced transaction usage in ORM
- Refactored cache module
- Exposed `get`, `set`, `get_or_set`, `clear` methods in `cache.Cache`
  and handlers objects
- Added decorator syntax support to cache module
- Added `response` method to cache module and relevant `cache` parameter in
  `app.App.route`, `app.App.module` and `app.AppModule.route` decorators
- Added `switch` method to `orm.objects.Set` to allow changing model context
- Rewritten sessions' managers
- Deprecated `SessionCookieManager`, `SessionFSManager` and
  `SessionRedisManager` classes in `sessions` module in favour of unified
  `SessionManager` wrapper and its `cookies`, `files` and `redis` methods


Version 1.1
-----------

Released on July 17th 2017, codename Lesath

- Several bugfixes
- Removed preload cache in templater to enhance extensions behavior
- Added `routes_paths` configuration in `Auth` module
- Added form widget for 'decimal' fields
- Avoid to guess 'Content-Type' response header from path extension
- Allow to use classmethods on `Field` class to specify types instead of
  string arguments


Version 1.0
-----------

Released on March 10th 2017, codename Izar

- Several bugfixes
- Moved routing handlers and helpers to pipeline logic
- Added support for app modules nesting and inheritance
- Added lambda notation to `Set.where` when involving just one model
- Rewritten `rowattr` and `rowmethod` injection logic
- Removed `bind_to_model` option from `rowattr` and `rowmethod`
- Optimized rows parsing in ORM adapters
- Improved caching techniques on selected records relations
- Added automatic casting of route variables
- Added support for float variable rules in routes
- Deprecated `dal` module in favour of `orm`
- Added support for multiple paths in routes
- Enhanced wsgi request handling performance
- Added `handle_static` boolean option to `App.config`
- Enhanced language recognition from Accept-Language header
- Optimized translator initialization
- Added `now` attribute and global method which returns `request.now` or
  `datetime.now` when request context is missing
- Added access to computed values within insert and update callbaks
- Deprecated `Model.form_rw` in favour of `Model.fields_rw`
- Optimized json and xml serializers, added optional `json_safe` serializer
  for old behavior
- Added `__json__` and `__xml__` methods handling in serializers for custom
  objects serialization
- Added `headers` attribute to `Request`
- Replaced udatetime dependency with pendulum
- `weppy.globals.now`, `isDatetime` validator and date route variables are now
  `Pendulum` objects
- Added support for additional separators apart from '/' between route
  variables route definitions
- Removed `extension` parameter in `url`
- Added `anchor` parameter in `url`
- Deprecated `tags` module in favour of `html`
- Optimized escaping code for html components
- Optimized templates caching
- Lightened the request flow
- Added signals to extensions
- Added application's defined commands in cli help listing
- Enhanced the json validator
- Refactored the `tools.mailer` module
- Refactored the `tools.auth` module
- The `Database` instance now performs auto connection using the
  `auto_connection` parameter or just in the cli environment if missing
- Automatic migrations on the database are now turned off by default


Version 0.8
-----------

Released on October 31st 2016, codename Hadar

- Several bugfixes
- Added readable fields handling in forms
- Enhanced HTTP errors on streaming
- Improved templater performance
- Added `dbset` option to `in` validator
- Ensuring `unique` validation is performed also without forms
- Better implementation for nested selection when using `join` and `including`
- Updated router to allow routes override
- Changed default serialization and validation of `datetime` fields to respect
  RFC3339 standard
- Updated postgres default adapters to latest available from pyDAL
- Changed `has_one` attributes when using `join` and `including`
  to not be lists
- Added support for 'bigint' fields in the migrator


Version 0.7
-----------

Released on June 7th 2016, codename Girtab

- Changed CLI 'shell' command to loads the entire application context
- Added `scope` option to `has_one` and `has_many` relations
- Added `where` option to `has_one` and `has_many` relations
- `@computation` and callbacks helpers now keep definition order
- Allow usage of `has_one` and `has_many` helpers as decorators to customize
  relations' sets generation
- Added default configuration for extensions
- Added `Model.new` method
- Added databse indexing support
- Added default validation for 'password' fields
- Added CLI 'routes' command
- Deprecated `@computation`, `@virtualfield` and `@fieldmethod` in favor of
  `@compute`, `@rowattr` and `@rowmethod`
- Updated `current_model_only` parameter of `@virtualfield` and `@fieldmethod`
  to `bind_to_model` in `@rowattr` and `@rowmethod`


Version 0.6
-----------

Released on January 25th 2016, codename Fornacis

- Several bugfixes
- Added `remove` method to `HasManySet` and `HasManyViaSet`
- Common handlers and helpers are now accessible via application object
- Introduced scopes in models
- Template reloader now checks also `include` and `extend` blocks
- Deprecated `expose()` in favor of `route()`
- Implemented `join` method on `Set`
- Reviewed `Auth` actions depending on user status
- Added support facilities to `Auth` in order to manage user status
- Implemented support for custom naming on `has_many`
- Added `current_model_only` option to `virtualfield` and `fieldmethod`
  decorators, default changed to `True`
- Introduced testing suite for applications
- Added `language` option to `url()`
- Implemented user status resync with database in `Auth` handler
- Implemented `refers_to` in dal apis
- Added 'self' keyword for self-relations in dal
- Changed `has_one` return value to `Set` in order to avoid n+1 queries
- Added `pagination` and `including` options to `Set.select()`
- Caching resultsets on `has_one` and `has_many` realtions calls for select
- Added `where`, `all`, `first`, `last` and `get` methods to `Model`
- Changed `add` method of `HasManySet` and `HasManyViaSet`
- Added `create` method to `HasOneSet`, `HasManySet` and `HasManyViaSet`
- Added `clear` method to session handlers for bulk invalidation
- Implemented a revision based migration engine on the database layer
- Deprecated `Request.vars`, `Request.get_vars` and `Request.post_vars` in
  favor of `Request.params`, `Request.query_params` and `Request.body_params`
- Deprecated `Form.vars` and `Form.input_vars` in favor of `Form.params` and
  `Form.input_params`
- Deprecated `url(vars={})` in favor of `url(params={})`


Version 0.5
-----------

Released on October 2nd 2015, codename Elnath

- Introduced python 3 support
- Introduced multiple inheritance support on `Model` class
- Added optional keyed arguments support to `HasManyViaSet.add` for additional
  columns on join tables
- Minor bugfixes


Version 0.4
-----------

Released on August 3rd 2015, codename Deneb

- Intruduced a real ORM inside weppy:
  - Consequent new features:
    - `belongs_to`, `has_one` and `has_many` apis for relations
    - Automatic joins of attributes defined with new apis
    - Cleaner `Model` definition syntax
    - New naming convention based on singular for model and plural for tables
    - Automatic tablenames based on `Model` classes' names
  - Consequent changes:
    - Fields are now defined as attributes of `Model`
    - Some `Field` types are now procesed also considering the pythonic naming
      ('integer' -> 'int', 'boolean' -> 'bool')
    - `Field` class doesn't accept 'name' (first) parameter anymore
    - `Model.entity` is now the more correct `Model.table`
    - `Form` and `DALForm` classes now accepts dictionaries of fields
      instead of lists
    - `Auth` module has tablenames changed to new naming convention
- Completely refactored validators
- Introduced new validation syntax using dictionaries
- `Auth` now includes virtualfields on session `user` object
- Dropped python 2.6.x support
- Bugfixes in forms
- Refactored `Auth` module
- Added `body` parameter to `abort` helper (optional)
- Updated jQuery to v1.11.3


Version 0.3
-----------

Released on April 1st 2015, codename Caph

- Various bugfixes
- Implemented streaming of pyDAL 'blob' fields
- Better implementation of `@virtualfield` and `@fieldmethod`
- Added caching system to templates
- Added auto-reloader for builtin wsgi server
- Added `on_end` method to `Handler` class
- Updated jQuery to v1.11.2


Version 0.2
-----------

Released on February 11th 2015, codename Bellatrix

- Several bugfixes
- JSON body parsing for incoming requests with POST method and 'application/
  json' headers
- `widget_select()` in forms use `represent` attribute of fields to render
  values
- Moved `Storage` class to new `sdict` one
- Using pyDAL instead of a separated fork inside code
- Unified `DAL`/`ModelsDAL` and `Auth`/`ModelsAuth` into new `DAL` and `Auth`
- `Model` class now has only one `setup` method instead of the old unnecessary
  list of `set_` methods
- Updated validators nomenclature to "camelcase"
- `stream_file()` in helpers now accept a path relative to application, the old
  one is now renamed in the more consistent `stream_dbfile()`
- Added `SessionFSManager` to store sessions' data on filesystem
- `Model` class inherits fields and properties on subclassing
- Added `service.xml` method to serve xml contents


Version 0.1
-----------

Released on October 21st 2014, codename Altair

First public preview release.
