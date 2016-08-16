import re
import sqlalchemy as sqla
import json
import api.references

# debug
import sys
import traceback
from api import parser
from api.parser import is_pg_qual, read_bool, read_pgid
from sqlalchemy.engine import reflection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy
from oeplatform.securitysettings import *
pgsql_qualifier = re.compile(r"^[\w\d_\.]+$")
_ENGINES = {}
from api import references
from sqlalchemy import func, MetaData, Table
from sqlalchemy.sql.ddl import CreateTable
import oeplatform.securitysettings as sec

Base = declarative_base()



def _get_table(db, schema, table):
    engine = _get_engine(db)
    metadata = MetaData()

    return Table(table, metadata, autoload=True, autoload_with=engine, schema=schema)

class DataStore(Base):
    __tablename__ = 'ckan_datastore'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True,
                           autoincrement=True)
    schema = sqlalchemy.Column(sqlalchemy.String(30))
    table = sqlalchemy.Column(sqlalchemy.String(30))
    resource = sqlalchemy.Column(sqlalchemy.String(40))
    dataset = sqlalchemy.Column(sqlalchemy.String(30))



def get_table_resource(schema, table):
    result = sqlalchemy.select(DataStore.c.resource, DataStore.c.dataset).where(
        DataStore.c.table == table, DataStore.c.schema == schema)
    if not result:
        return None
    else:
        return result.first()


def comment_table_create(session, schema, table):
    session.execute("create table {schema}{table}_cor (like _comment_base including all) inherits (_comment_base)".format(schema=schema + "." if schema else "", table="_"+table))
    #session.execute("alter table {schema}{table}_cor add primary key using index")


def comment_table_drop(session, schema, table):
    session.execute("drop table {schema}{table}_cor".format(schema=schema + "." if schema else "", table="_"+table))


def table_create(request):
    # TODO: Authentication
    # TODO: column constrains: Unique,
    # load schema name and check for sanity
    engine = _get_engine()
    connection = engine.connect()

    schema = read_pgid(request.POST["schema"])
    create_schema = not has_schema(request)
    # Check whether schema exists

    # load table name and check for sanity
    table = read_pgid(request.POST.pop("table"))

    # Process fields
    fieldstrings = []
    fields = request.POST.pop("fields", [])
    foreign_keys = []
    primary_keys = []
    for field in fields:
        fname = read_pgid(field["name"])
        type_name = field["type"]

        # TODO: check whether type_name is an actual postgres type
        # if not engine.dialect.has_type(connection,type_name):
        #    raise p.toolkit.ValidationError("Invalid field type: '%s'"% type_name )
        fieldstrings.append(field["name"] + " " + type_name)
        if "pk" in field:
            if read_bool(field["pk"]):
                primary_keys.append([field["name"]])

    table_constraints = {"unique": [], "pk": primary_keys, "fk": foreign_keys}
    for con in request.POST.pop('constraints', []):
        if con['name'].lower() == "fk":
            for fk in con['constraint']:
                if not all(map(is_pg_qual,
                               [fk["schema"], fk["table"], fk["field"]])):
                    raise parser.ValidationError("Invalid identifier")
                if fk["on delete"].lower() not in ["cascade", "no action",
                                                   "restrict", "set null",
                                                   "set default"]:
                    raise parser.ValidationError("Invalid action")
                foreign_keys.append(([field["name"]],
                                     fk["schema"],
                                     fk["table"],
                                     fk["field"],
                                     fk["on delete"]))

    fieldstrings.append("_comment int")


    foreign_keys.append(("_comment", schema, "_"+table+"_cor", "id", "no action"))
    fk_constraints = []
    for (
            fk_field1, fk_schema, fk_table, fk_field2,
            fk_on_delete) in foreign_keys:
        fk_constraints.append(
            "constraint {field1}_{schema}_{table}_{field2}_fk foreign key ({field1}) references {schema}.{table} ({field2}) match simple on update no action on delete {ondel}".format(
                field1=fk_field1, schema=fk_schema, table=fk_table,
                field2=fk_field2, ondel=fk_on_delete)
        )
    constraints = ", ".join(fk_constraints)
    fields = "(" + (
    ", ".join(fieldstrings + fk_constraints) if fieldstrings else "") + ")"
    sql_string = "create table {schema}.{table} {fields} {constraints}".format(
        schema=schema, table=table, fields=fields, constraints="")

    create_dict = {'name': table}
    # resource_dict = p.toolkit.get_action('resource_create')(
    # context, request.POST['resource'])

    # TODO: Add author/maintainer, tags, license

    resource_dict = None
    session = sessionmaker(bind=engine)()
    try:
        if create_schema:
            session.execute("create schema %s" % schema)
        comment_table_create(session, schema, table)
        session.execute(sql_string.replace('%', '%%'))

    except Exception as e:
        traceback.print_exc()
        session.rollback()
        raise e
    else:
        session.commit()
    return {'success': True}

def data_delete(request):
    raise NotImplementedError()


def table_drop(request):
    db = request.POST["db"]
    engine = _get_engine(db)
    connection = engine.connect()

    # load schema name and check for sanity    
    schema = request.POST.pop("schema", "public")
    if not is_pg_qual(schema):
        return {'success':False, 'reason':'Invalid schema name: %s'%schema}
        # Check whether schema exists

    # load table name and check for sanity
    table = request.POST.pop("table", None)

    if not is_pg_qual(table):
        return {'success': False, 'reason': 'Invalid table name: %s' % table}

    try:
        exists = bool(request.POST.pop("exists", False))
    except:
        return {'success': False,
                'reason': 'Invalid exists clause: %s' % exists}

    option = request.POST.pop("option", None)
    if option and option.lower() not in ["cascade", "restrict"]:
        return {'success': False, 'reason': 'Invalid option clause name: %s' % option}

    sql_string = "drop table {exists} {schema}.{table} {option} ".format(
        schema=schema,
        table=table,
        option=option if option else "",
        exists="IF EXISTS" if exists else "")

    session = sessionmaker(bind=engine)()
    try:
        session.execute(sql_string.replace('%', '%%'))
        comment_table_drop(session, schema, table)
    except Exception as e:
        traceback.print_exc()
        session.rollback()
        raise e
    else:
        session.commit()

    return {}

def data_search(context, request):
    engine = _get_engine()
    connection = engine.connect()
    query = parser.parse_select(request.POST)
    result = connection.execute(query)
    description = result.context.cursor.description
    data = [list(r) for r in result]
    return {'data': data,
            'description': [[col.name, col.type_code, col.display_size,
                             col.internal_size, col.precision, col.scale,
                             col.null_ok] for col in description]}


def _get_count(q):
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count


def count_all(db, schema, table):
    engine = _get_engine(db)
    session = sessionmaker(bind=engine)()
    t = _get_table(db, schema, table)
    return session.query(t).count()#_get_count(session.query(t))

def _get_header(results):
    header = []
    for field in results.cursor.description:
        header.append({
            'id': field[0],#.decode('utf-8'),
            'type': field[1]
        })
    return header


def analyze_columns(db, schema, table):
    engine = _get_engine(db)
    connection = engine.connect()
    result = connection.execute(
        "select column_name as id, data_type as type from information_schema.columns where table_name = '{table}' and table_schema='{schema}';".format(
            schema=schema, table=table))
    return [{'id':r['id'],'type':r['type']} for r in result]

def search(db, schema, table, fields=None, pk = None, offset = 0, limit = 100):
    if not fields:
        fields = '*'
    else:
        fields = ', '.join(fields)
    engine = _get_engine(db)
    connection = engine.connect()
    refs = connection.execute(references.Entry.__table__.select())

    sql_string = "select {fields} from {schema}.{table}".format(
        schema=schema, table=table, fields=fields)

    if pk:
         sql_string += " where {} = {}".format(pk[0],pk[1])

    sql_string += " limit {}".format(limit)
    sql_string += " offset {}".format(offset)
    return connection.execute(sql_string, ), [dict(refs.first()).items()]


def clear_dict(d):
    return {
    k.replace(" ", "_"): d[k] if not isinstance(d[k], dict) else clear_dict(
        d[k]) for k in d}


def get_comment_table(db, schema, table):
    engine = _get_engine(db)
    connection = engine.connect()

    sql_string = "select obj_description('{schema}.{table}'::regclass::oid, 'pg_class');".format(
        schema=schema, table=table)

    res = connection.execute(sql_string)
    if res:
        jsn = res.first().obj_description
        if jsn:
            jsn = jsn.replace('\n','')
        else:
            return {}
        try:
            return json.loads(jsn)
        except ValueError:
            return{'error': 'No json format', 'content': jsn}
    else:
        return {}


def data_insert(request):
    engine = _get_engine()
    # load schema name and check for sanity    
    schema = request.POST["schema"]

    if not is_pg_qual(schema):
        raise parser.ValidationError("Invalid schema name")
        # Check whether schema exists

    # load table name and check for sanity
    table = request.POST.pop("table", None)
    if not is_pg_qual(table):
        raise parser.ValidationError("Invalid table name")

    fields = request.POST.pop("fields", "*")
    if fields != "*" and not all(map(is_pg_qual, fields)):
        raise parser.ValidationError("Invalid field name")
    fieldsstring = "(" + (", ".join(fields)) + ")" if fields != "*" else ""

    if bool(request.POST.pop("default", False)):
        data = " DEFAULT VALUES"
    else:
        data = request.POST.pop("values", [])

    returning = request.POST.pop("returning", '')
    if returning:
        returning = 'returning ' + ', '.join(map(parser.parse_expression, returning))

    connection = engine.connect()

    result = connection.execute(
        "INSERT INTO {schema}.{table} {fields} VALUES{markers} {returning}".format(
            schema=schema, table=table, fields=fieldsstring,
            markers="(" + (",".join("%s" for i in range(len(data[0])))) + ")",
            returning=returning),
        data)
    if returning:
        description = result.context.cursor.description
        data = [list(r) for r in result]
        return {'data': data,
                'description': [[col.name, col.type_code, col.display_size,
                                 col.internal_size, col.precision, col.scale,
                                 col.null_ok] for col in description]}
    else:
        return request.POST


def data_info(context, request):
    return request.POST


def connect():
    engine = _get_engine()
    insp = sqla.inspect(engine)
    return insp

def _get_engine():
    engine = sqla.create_engine(
        'postgresql://{0}:{1}@{2}:{3}/{4}'.format(
            sec.dbuser,
            sec.dbpasswd,
            sec.dbhost,
            sec.dbport,
            sec.dbname))
    return engine


def has_schema(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.has_schema(engine.connect(), request.POST['schema'])
    return result


def has_table(context, request):
    engine = _get_engine(request.POST['db'])
    schema= request.POST.pop('schema', None)
    table = request.POST['table_name']
    result = engine.dialect.has_table(engine.connect(), table,
                                      schema=schema)
    return result


def has_sequence(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.has_sequence(engine.connect(),
                                         request.POST['sequence_name'],
                                         schema=request.POST.pop('schema', None))
    return result


def has_type(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.has_schema(engine.connect(),
                                       request.POST['sequence_name'],
                                       schema=request.POST.pop('schema', None))
    return result


@reflection.cache
def get_table_oid(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_table_oid(engine.connect(),
                                          request.POST['table_name'],
                                          schema=request.POST['schema'],
                                          **request.POST)
    return result


@reflection.cache
def get_schema_names(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_schema_names(engine.connect(), **request.POST)
    return result


@reflection.cache
def get_table_names(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_table_names(engine.connect(),
                                            schema=request.POST.pop('schema',
                                                                 None),
                                            **request.POST)
    return result


@reflection.cache
def get_view_names(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_view_names(engine.connect(),
                                           schema=request.POST.pop('schema', None),
                                           **request.POST)
    return result


@reflection.cache
def get_view_definition(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_schema_names(engine.connect(),
                                             request.POST['view_name'],
                                             schema=request.POST.pop('schema',
                                                                  None),
                                             **request.POST)
    return result


@reflection.cache
def get_columns(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_columns(engine.connect(),
                                        request.POST['table_name'],
                                        schema=request.POST.pop('schema', None),
                                        **request.POST)
    return result


@reflection.cache
def get_pk_constraint(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_pk_constraint(engine.connect(),
                                              request.POST['table_name'],
                                              schema=request.POST.pop('schema',
                                                                   None),
                                              **request.POST)
    return result


@reflection.cache
def get_foreign_keys(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_foreign_keys(engine.connect(),
                                             request.POST['table_name'],
                                             schema=request.POST.pop('schema',
                                                                  None),
                                             postgresql_ignore_search_path=request.POST.pop(
                                                 'postgresql_ignore_search_path',
                                                 False),
                                             **request.POST)
    return result


@reflection.cache
def get_indexes(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_indexes(engine.connect(),
                                        request.POST['table_name'],
                                        request.POST['schema'],
                                        **request.POST)
    return result


@reflection.cache
def get_unique_constraints(context, request):
    engine = _get_engine(request.POST['db'])
    result = engine.dialect.get_foreign_keys(engine.connect(),
                                             request.POST['table_name'],
                                             schema=request.POST.pop('schema',
                                                                  None),
                                             **request.POST)
    return result
