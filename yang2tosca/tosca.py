"""pyang plug-in to convert YANG schema definitions to TOSCA data
types

"""

import optparse
import logging

from pyang import plugin
from pyang import statements
from pyang import types
from pyang import error

from datetime import datetime

import re
import textwrap

import stringcase

# Import config file support
import yang2tosca.config.config as cfg

# TOSCA namespace for built-in IETF types
IETF_NAMESPACE = 'org.ietf:1.0'
IETF_NAMESPACE_PREFIX = 'inet'

# Regular expressions for parsing YANG range and length
# expressions. Copied from pyang's syntax.py file
length_str = '((min|max|[0-9]+)\s*' \
             '(\.\.\s*' \
             '(min|max|[0-9]+)\s*)?)'
length_expr = length_str + '(\|\s*' + length_str + ')*'
re_length_part = re.compile(length_str)
range_str = '((\-INF|min|max|((\+|\-)?[0-9]+(\.[0-9]+)?))\s*' \
            '(\.\.\s*' \
            '(INF|min|max|(\+|\-)?[0-9]+(\.[0-9]+)?)\s*)?)'
range_expr = range_str + '(\|\s*' + range_str + ')*'
re_range_part = re.compile(range_str)

# Regular expressions for parsing YAML timestamps. Copied from
# constructor.py in ruamel package
timestamp_regexp = re.compile(
    u'''^(?P<year>[0-9][0-9][0-9][0-9])
      -(?P<month>[0-9][0-9]?)
      -(?P<day>[0-9][0-9]?)
      (?:((?P<t>[Tt])|[ \\t]+)   # explictly not retaining extra spaces
      (?P<hour>[0-9][0-9]?)
      :(?P<minute>[0-9][0-9])
      :(?P<second>[0-9][0-9])
      (?:\\.(?P<fraction>[0-9]*))?
      (?:[ \\t]*(?P<tz>Z|(?P<tz_sign>[-+])(?P<tz_hour>[0-9][0-9]?)
      (?::(?P<tz_minute>[0-9][0-9]))?))?)?$''', re.X)


def pyang_plugin_init():
    plugin.register_plugin(ToscaPlugin())


#########################################################################    
# TOSCA plug-in object
#########################################################################    

class ToscaPlugin(plugin.PyangPlugin):

    def add_output_format(self, fmts):
        """Add an output format to the pyang program.

        `fmts` is a dict which maps the format name string to a plugin
        instance.
        """
        fmts['tosca'] = self

        return


    def add_opts(self, optparser):
        """Add tosca-specific command line options to the pyang program.
        """

        optlist = [
            optparse.make_option('--tosca-debug',
                                 dest='tosca_debug',
                                 action="store_true",
                                 help='TOSCA debug'),
            optparse.make_option('--camel-case',
                                 dest='camel_case',
                                 action="store_true",
                                 help='Use camel case capitalization style'),
            optparse.make_option('--tosca-config-file',
                                 dest='tosca_config_file',
                                 help='Configuraton file for TOSCA translator'),
            ]

        group = optparser.add_option_group("TOSCA specific options")
        group.add_options(optlist)
        return

    #########################################################################    
    # Plug-in setup
    #########################################################################    

    def setup_ctx(self, ctx):
        """Modify the Context before the module repository is accessed (This
        is done for all plugins).

        """
        if ctx.opts.tosca_debug:
            print("Setting up context for all plugins")
        # Do nothing
        return

    def setup_fmt(self, ctx):
        """Modify the Context at setup time.  Called for the selected plugin.
        """
        # Read config file
        tosca_config = cfg.read_tosca_config(ctx.opts.tosca_config_file)

        # Extract type map
        try:
            ctx.type_map = tosca_config['type_map']
        except (KeyError, TypeError):
            ctx.type_map = dict()
        return

    def pre_load_modules(self, ctx):
        """Called for the selected plugin, before any modules are loaded"""
        if ctx.opts.tosca_debug:
            print("Loading modules for TOSCA")
        return

    def pre_validate_ctx(self, ctx, modules):
        """Called for all plugins, before the modules are validated"""
        if ctx.opts.tosca_debug:
            print("Before validating for all plugins")
        return

    def pre_validate(self, ctx, modules):
        """Called for the selected plugin, before the modules are validated"""
        if ctx.opts.tosca_debug:
            print("Before validating for TOSCA plugin")
        return

    def post_validate(self, ctx, modules):
        """Called for the selected plugin, after the modules
        have been validated"""
        if ctx.opts.tosca_debug:
            print("Done validating for TOSCA plugin")
        return

    def post_validate_ctx(self, ctx, modules):
        """Called for all plugins, after the modules
        have been validated"""
        if ctx.opts.tosca_debug:
            print("Done validating for plugins")
        return

    def emit(self, ctx, modules, fd):
        """Produce the tosca output.

        Raise error.EmitError on failure.
        """
        if ctx.opts.tosca_debug:
            logging.basicConfig(level=logging.DEBUG)

        # Write all modules
        for module in modules:
            emit_module(ctx, module, fd, '')


#########################################################################    
# Top-level method that generates a TOSCA definitions file
#########################################################################    

def emit_module(ctx, stmt, fd, indent):
    """Convert a YANG module to TOSCA by (recursively) converting each of
    the YANG statements in the YANG module to TOSCA.

    Note that for each YANG statement, we keep track of which
    sub-statements are handled by 'yang2tosca', and we inform the user
    about any sub-statements that are not yet handled.
    """

    # Sub-statements for the (sub)module statement:
    # (See https://datatracker.ietf.org/doc/html/rfc7950)
    #
    # anydata       0..n        
    # anyxml        0..n        
    # augment       0..n        
    # belongs-to    1           
    # choice        0..n        
    # contact       0..1        
    # container     0..n        
    # description   0..1        
    # deviation     0..n        
    # extension     0..n        
    # feature       0..n        
    # grouping      0..n        
    # identity      0..n        
    # import        0..n        
    # include       0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # namespace     1           
    # notification  0..n        
    # organization  0..1        
    # prefix        1           
    # reference     0..1        
    # revision      0..n        
    # rpc           0..n        
    # typedef       0..n        
    # uses          0..n        
    # yang-version  1           

    # Emit tosca header
    fd.write("tosca_definitions_version: tosca_simple_yaml_1_3\n\n")
    
    # Add comment
    fd.write(
        "# This template was auto-generated by yang2tosca from the YANG module '%s'\n\n"
        % stmt.arg
    )
    
    # Emit description:
    description = stmt.search_one("description")
    if description:
        emit_description(ctx, description, fd, indent)
        fd.write("\n")

    # Emit metadata
    emit_metadata(ctx, stmt, fd, indent)
    fd.write("\n")

    # Emit imports and includes
    emit_imports_and_includes(ctx, stmt, fd, indent)
    fd.write("\n")

    # Beginning of data type definition section
    fd.write("data_types:\n\n")
    indent = indent + '  '

    # Emit data types defined in this module
    emit_data_types_in_stmt(ctx, stmt, fd, indent)

    # Sanity checking. To be removed later
    handled = [
        'augment',
        'belongs-to',
        'contact',
        'container',
        'description',
        'feature',
        'grouping',
        'import',
        'include',
        'list',
        'namespace',
        'organization',
        'prefix',
        'reference',
        'revision',
        'typedef',
        'uses',
        'yang-version'
    ]
    check_substmts(stmt, handled)


#########################################################################    
# Generate TOSCA description
#########################################################################    

def emit_description(ctx, stmt, fd, indent):

    # Emit description key
    fd.write(
        "%sdescription: "
        % (indent)
    )
    # Emit text. Split into multiple lines if necessary
    lines = wrap_text(stmt.arg)
    emit_text_string(ctx, lines, fd, indent)

    handled = []
    check_substmts(stmt, handled)


def wrap_text(text_string):
    """Split a text string into multiple lines to improve legibility
    """
    # First, check to see if the text was already formatted. We do
    # this by trying to split the text string into mutliple lines
    # based on newlines contained in the string.
    lines = text_string.splitlines()
    if len(lines) > 1:
        # Already formatted
        return lines

    # Not already formatted. Wrap it ourselves.
    return textwrap.wrap(text_string)


def emit_text_string(ctx, lines, fd, indent):
    """Write a text value. We use YAML folded style if the text consists
    of multiple lines or if it includes a colon character (or some
    other character that would violate YAML syntax)
    """
    if not lines:
        lines = [""]
    if len(lines) > 1 or (':' in lines[0]) or ('\'' in lines[0]):
        # Emit folding character
        fd.write(">-\n")
        # Emit individual lines. Make sure the first line is indented
        # correctly.
        first = True
        for line in lines:
            if first:
                fd.write(
                    "%s%s\n"
                    % (indent + '  ', line.lstrip())
                )
                first = False
            else:
                fd.write(
                    "%s%s\n"
                    % (indent + '  ', line.lstrip())
                )
    else:
        fd.write("%s\n"
                 % lines[0]
        )


#########################################################################    
# Generate TOSCA metadata
#########################################################################    

def emit_metadata(ctx, stmt, fd, indent):
    """YANG statements that do not have a TOSCA equivalent are translated
    into TOSCA metadata.
    """

    yang_version = stmt.search_one('yang-version')
    organization = stmt.search_one('organization')
    contact = stmt.search_one('contact')
    namespace = stmt.search_one("namespace")
    prefix = stmt.search_one("prefix")
    belongs_to = stmt.search_one('belongs-to')
    revisions = stmt.search('revision')
    reference = stmt.search_one('reference')
    features = stmt.search('feature')

    if yang_version or organization or contact or reference \
       or len(revisions) or len(features) or namespace or prefix:
        fd.write(
            "%smetadata:\n"
            % indent
        )
        indent = indent + '  '
        if yang_version: 
            emit_yang_version(ctx, yang_version, fd, indent)
        if organization: 
            emit_organization(ctx, organization, fd, indent)
        if contact: 
            emit_contact(ctx, contact, fd, indent)
        if namespace:
            emit_namespace(ctx, namespace, fd, indent)
        if prefix:
            emit_prefix(ctx, prefix, fd, indent)
        if belongs_to:
            emit_belongs_to(ctx, belongs_to, fd, indent)
        if len(revisions):
            emit_revisions(ctx, revisions, fd, indent)
        if reference: 
            emit_reference(ctx, reference, fd, indent)
        if len(features):
            emit_features(ctx, features, fd, indent)


def emit_yang_version(ctx, stmt, fd, indent):
    fd.write(
        "%syang-version: %s\n"
        % (indent, stmt.arg)
    )
    handled = []
    check_substmts(stmt, handled)


def emit_organization(ctx, stmt, fd, indent):
    fd.write(
        "%sorganization: "
        % (indent)
    )
    lines = wrap_text(stmt.arg)
    emit_text_string(ctx, lines, fd, indent)
    handled = []
    check_substmts(stmt, handled)


def emit_contact(ctx, stmt, fd, indent):
    fd.write(
        "%scontact: "
        % (indent)
    )
    lines = wrap_text(stmt.arg)
    emit_text_string(ctx, lines, fd, indent)
    handled = []
    check_substmts(stmt, handled)


def emit_namespace(ctx, stmt, fd, indent):
    fd.write(
        "%snamespace: %s\n"
        % (indent, stmt.arg)
    )


def emit_prefix(ctx, stmt, fd, indent):
    fd.write(
        "%s# TOSCA does not support prefix for local namespaces\n"
        % indent
    )
    fd.write(
        "%sprefix: %s\n"
        % (indent, stmt.arg)
    )
    # Track local prefix in context since we may need it later
    ctx.local_prefix = stmt.arg


def emit_belongs_to(ctx, stmt, fd, indent):
    # Sub-statements for the belongs_to statement:
    #
    # prefix        1           
    fd.write(
        "%sbelongs-to: %s\n"
        % (indent, stmt.arg)
    )


def emit_revisions(ctx, revisions, fd, indent):
    fd.write(
        "%srevisions:\n"
        % indent
    )
    for revision in revisions:
        emit_revision(ctx, revision, fd, indent + '  ')


def emit_revision(ctx, stmt, fd, indent):

    # Sub-statements for the revision statement:
    #
    # description   0..1        
    # reference     0..1        
    description = stmt.search_one('description')
    reference = stmt.search_one('reference')
    handled = [
        'description',
        'reference'
    ]
    check_substmts(stmt, handled)

    if not description and not reference:
        return

    # Emit the revision
    fd.write(
        "%s'%s':\n"
        % (indent, stmt.arg)
    )
    indent = indent + '  '
    if description:
        emit_description(ctx, description, fd, indent)
    if reference:
        emit_reference(ctx, reference, fd, indent)


def emit_reference(ctx, stmt, fd, indent):

    # Check if text needs to be wrapped
    lines = wrap_text(stmt.arg)

    # Emit reference key
    fd.write(
        "%sreference: "
        % (indent)
    )
    # Emit text
    emit_text_string(ctx, lines, fd, indent)

    handled = []
    check_substmts(stmt, handled)


def emit_features(ctx, features, fd, indent):
    fd.write(
        "%sfeatures:\n"
        % indent
    )
    for feature in features:
        emit_feature(ctx, feature, fd, indent + '  ')


def emit_feature(ctx, stmt, fd, indent):
    # Sub-statements for the feature statement:
    #
    # description   0..1        
    # if-feature    0..n        
    # reference     0..1        
    # status        0..1        
    description = stmt.search_one('description')
    reference = stmt.search_one('reference')
    status = stmt.search_one('status')

    handled = [
        'description',
        'reference',
        'status'
    ]
    check_substmts(stmt, handled)

    if not description and not reference and not status:
        return

    # Emit the feature
    fd.write(
        "%s'%s':\n"
        % (indent, stmt.arg)
    )
    indent = indent + '  '
    if description:
        emit_description(ctx, description, fd, indent)
    if reference:
        emit_reference(ctx, reference, fd, indent)
    if status:
        emit_status(ctx, status, fd, indent)


def emit_status(ctx, stmt, fd, indent):
    # Emit status key
    fd.write(
        "%sstatus: %s"
        % (indent, stmt.arg)
    )

#########################################################################    
# Generate TOSCA import statements
#########################################################################    

def emit_imports_and_includes(ctx, stmt, fd, indent):
    """Both YANG 'import' and 'include' statements are translated into
    TOSCA import statements. However, YANG 'include' statements do not
    use a namespace prefix. Instead, definitions from the 'included'
    YANG files are created in the namespace of the importing TOSCA
    file
    """
    imports = stmt.search('import')
    includes = stmt.search('include')
    
    fd.write(
        "imports:\n"
    )
    indent = indent + '  '
    # Always import built-in YANG types
    fd.write(
        "%s- file: %s\n%s  namespace_prefix: %s\n"
        % (indent, IETF_NAMESPACE, indent, IETF_NAMESPACE_PREFIX)
    )
    # Add imports 
    for imprt in imports:
        emit_import_or_include(ctx, imprt, fd, indent)
    # Add includes
    for include in includes:
        emit_import_or_include(ctx, include, fd, indent)


def emit_import_or_include(ctx, stmt, fd, indent):

    # Sub-statements for the import statement:
    #
    # description    0..1        
    # prefix         1           
    # reference      0..1        
    # revision-date  0..1        

    # TOSCA will import the module by its namespace name.  First, find
    # the imported module from the context
    imported_module = ctx.get_module(stmt.arg)
    imported_module_name = stmt.arg + '.yaml'

    if imported_module is not None:
        # Find namespace of imported module
        imported_namespace = imported_module.search_one("namespace")
        if imported_namespace is not None:
            imported_namespace_name = imported_namespace.arg
        else:
            imported_namespace_name = None
    else:
        imported_namespace_name = None
        
    # Emit import statement
    prefix = stmt.search_one('prefix')
    if prefix or imported_namespace_name:
        fd.write(
            "%s- file: %s\n"
            % (indent, imported_module_name)
        )
        fd.write(
            "%s  namespace_prefix: %s\n"
            % (indent, prefix.arg)
        )
        if imported_namespace_name:
            fd.write(
                "%s  # namespace: %s\n"
                % (indent, imported_namespace_name)
        )
    else:
        fd.write(
            "%s- %s\n"
            % (indent, imported_module_name)
        )
    handled = ['prefix']
    check_substmts(stmt, handled)


#########################################################################    
# Generate TOSCA data type definitions
#########################################################################    

def emit_data_types_in_stmt(ctx, stmt, fd, indent):
    """Emit TOSCA data types for substatements of this statement. Data
    type definitions are generated for each of the following YANG
    statements:

    - typedef
    - grouping
    - container
    - list (to be used as the entry_schema for the list)
    - choice
    - augment (at the module level)
    - augment (within uses statement)

    """

    # Emit data type definitions for 'typedef' statements
    typedefs = stmt.search('typedef')
    for typedef in typedefs:
        emit_typedef(ctx, typedef, fd, indent)
        fd.write("\n")

    # Emit data type definitions for 'grouping' statements
    groupings = stmt.search('grouping')
    for grouping in groupings:
        emit_grouping(ctx, grouping, fd, indent)
        fd.write("\n")

    # Emit data type definitions for 'container' statements
    containers = stmt.search('container')
    for container in containers:
        # If a container has a single 'uses' statement only, there is
        # no need to create a separate data type for it. We'll just
        # use the data type for the 'grouping' specified in the 'uses'
        # statement.
        if not has_single_uses_stmt_only(container):
            emit_data_type(ctx, container, fd, indent)
            fd.write("\n")

    # Emit data type definitions for 'list' statements
    lists = stmt.search('list')
    for lst in lists:
        # If a container has a single 'uses' statement only, there is
        # no need to create a separate data type for it. We'll just
        # use the data type for the 'grouping' specified in the 'uses'
        # statement.
        if not has_single_uses_stmt_only(lst):
            emit_data_type(ctx, lst, fd, indent)
            fd.write("\n")

    # Emit data type definitions underneath 'uses' statements
    usess = stmt.search('uses')
    for uses in usess:
        augments = uses.search('augment')
        for augment in augments:
            print("Warning: review <%s> augments <%s>" % (augment.arg, uses.arg))
            emit_data_type(ctx, augment, fd, indent)
            fd.write("\n")

    # Handle type definitions underneath 'choice' statements 
    choices = stmt.search('choice')
    for choice in choices:
        cases = choice.search('case')
        for case in cases:
            emit_data_types_in_stmt(ctx, case, fd, indent)

    # Handle type definitions based on 'augment' statements
    augmentations = stmt.search('augment')
    for augment in augmentations:
        emit_augmented_type(ctx, augment, fd, indent)
        fd.write("\n")


def emit_typedef(ctx, stmt, fd, indent):
    """Create a TOSCA data type definition from a YANG 'typedef'
    statement"""

    # Sub-statements for the typedef statement:
    #
    # default       0..1        
    # description   0..1        
    # reference     0..1        
    # status        0..1        
    # type          1           
    # units         0..1        

    derived_from = stmt.search_one('type')
    units = stmt.search_one('units')
    default = stmt.search_one('default')
    description = stmt.search_one('description')

    # Find name for this data type
    name = stmt.arg

    # # Write out data type
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    if description:
        emit_description(ctx, description, fd, indent)
    if derived_from:
        emit_derived_from(ctx, derived_from, fd, indent)
    if units:
        emit_units(ctx, units, fd, indent)
    if default:
        emit_commented_default(ctx, default, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)

    handled = [
        'default',
        'description',
        'reference',
        'type',
        'units',
    ]
    check_substmts(stmt, handled)


def emit_grouping(ctx, stmt, fd, indent):
    """Create a TOSCA data type definition from a YANG 'grouping'
    statemen. This methods is just a wrapper around emit_data_type so
    we can check_substmts here.
    """

    # Sub-statements for the grouping statement:
    #
    # action        0..n        
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # container     0..n        
    # description   0..1        
    # grouping      0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # notification  0..n        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    # uses          0..n        

    emit_data_type(ctx, stmt, fd, indent)

    handled = [
        'choice',
        'container',
        'description',
        'grouping',
        'leaf',
        'leaf-list',
        'list',
        'reference',
        'typedef',
        'uses'
    ]
    check_substmts(stmt, handled)


def has_single_uses_stmt_only(stmt):
    """Check to see if this statement has exactly one 'uses' substatement
    without defining its own properties
    """

    # First, check 'uses' substatements
    usess = stmt.search('uses')
    if len(usess) != 1:
        return False

    # Then check local property definitions
    for sub in stmt.substmts:
        if sub.keyword in ['leaf','leaf-list','list','container','choice','augment']:
            return False

    # Has single uses statement only
    return True


def get_single_uses_stmt_grouping(ctx, stmt):
    """If a statement defines exactly on 'uses' substatement, return the
    name of the grouping to which the 'uses' refers.
    """
    # Get the 'uses' substatements
    usess = stmt.search('uses')
    return create_qualified_name(ctx, usess[0].arg)


def emit_data_type(ctx, stmt, fd, indent):
    """Create a TOSCA data type definition from a YANG statement. This
    method is used for 'container', 'grouping', and 'list'
    statements. These statements are different from other YANG
    statements since they result in two different types of TOSCA
    entities:

    - They result in a corresponding TOSCA data type
    - They result in a corresponding TOSCA property definition (within
      some other data type definition)

    As a result, these YANG statements are processed twice (in two
    different passes). Rather than calling 'check_substmt' here, we
    call it in the method that emits the property definition.
    """

    # First, recurse to make sure all other typedefs, containers,
    # lists, groupings, choices, and augments defined underneath this
    # statement are reflected into top-level TOSCA data type
    # definitions.
    emit_data_types_in_stmt(ctx, stmt, fd, indent)

    # Find the name for this data type
    name = stmt.arg

    # Write out a data type definition for this statement
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)

    # We use the grouping name specified in the first 'uses' statement
    # as the name of the TOSCA parent type
    uses = stmt.search('uses')
    if len(uses):
        emit_uses_derived_from(ctx, stmt, uses[0], fd, indent)
    # Emit constraints
    when = stmt.search_one('when')
    if when:
        emit_when(ctx, when, fd, indent)
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)

    # First add property definitions if necessary
    has_props = has_properties(stmt)
    if has_props:
        fd.write(
            "%sproperties:\n"
            % (indent)
        )
        emit_properties(ctx, stmt, fd, indent+'  ', prop=True)

        # If we have more than one uses statement, we'll just copy the
        # property definitions from the grouping specified in each
        # remaining 'uses' statement
        if len(uses) > 1:
            emit_uses_properties(ctx, stmt, uses[1:], fd, indent+'  ')

    # If necessary add attribute definitions (marked using "config false" in
    # YANG). Note that TOSCA data type definitions do not support
    # attributes. We just mark which property definitions need to be
    # converted to attribute definitions when TOSCA data types are
    # converted to node types.
    if has_attributes(stmt):
        fd.write("%s# TOSCA data types do not support attributes\n"
                 % (indent)
                 )
        fd.write("%s# Enable attributes when converting to a node type\n"
                 % (indent)
                 )

        if not has_props:
            # We have not previously emitted the 'properties' key
            fd.write(
                "%sproperties:\n"
                % (indent)
            )
        fd.write(
            "%s# attributes:\n"
            % (indent)
        )
        emit_properties(ctx, stmt, fd, indent+'  ', prop=False)

    # If we have more than one uses statement, we'll just add the
    # attributes from the grouping specified in each 'uses' statement
    if len(uses) > 1:
        emit_uses_attributes(ctx, stmt, uses[1:], fd, indent+'  ')


def emit_augmented_type(ctx, stmt, fd, indent):
    """Create a TOSCA data type definition from a YANG 'augment' statement
    in the top-level module. This method creates a TOSCA data type
    that derives from the TOSCA data type that corresponds to the
    entity being augmented.
    """

    # Sub-statements for the augment statement:
    #
    # action        0..n        
    # anydata       0..n        
    # anyxml        0..n        
    # case          0..n        
    # choice        0..n        
    # container     0..n        
    # description   0..1        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # notification  0..n        
    # reference     0..1        
    # status        0..1        
    # uses          0..n        
    # when          0..1        

    # First, recurse to make sure all other typedefs, containers, and
    # groupings defined underneath this statement are reflected in
    # top-level data type
    emit_data_types_in_stmt(ctx, stmt, fd, indent)

    # Find qualified name for this data type
    name = stmt.i_target_node.arg

    # Write out a data type definition for this statement
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)

    if_feature = stmt.search_one('if-feature')
    if if_feature:
        emit_if_feature(ctx, if_feature, fd, indent)

    # Find the TOSCA data type from which this type derives
    path = stmt.arg.split('/')
    if path[0]:
        print("Augment does not specify an absolute path")
    derived_from = create_qualified_name(ctx, path[-1])
    fd.write(
        "%sderived_from: %s\n"
        % (indent, derived_from)
    )

    emit_metadata(ctx, stmt, fd, indent)

    # Emit constraints
    when = stmt.search_one('when')
    if when:
        emit_when(ctx, when, fd, indent)
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)

    # Add properties
    fd.write(
        "%sproperties:\n"
        % (indent)
    )
    emit_properties(ctx, stmt, fd, indent+'  ', prop=True)

    # If we have uses statements, we'll just add the properties from
    # the grouping specified in each 'uses' statement
    uses = stmt.search('uses')
    if len(uses):
        emit_uses_properties(ctx, stmt, uses, fd, indent+'  ')

    # Next add attributes if necessary
    if has_attributes(stmt):
        fd.write("%s# TOSCA data types do not support attributes\n"
                 % (indent)
                 )
        fd.write("%s# Enable attributes when converting to a node type\n"
                 % (indent)
                 )

        fd.write(
            "%s# attributes:\n"
            % (indent)
        )
        emit_properties(ctx, stmt, fd, indent+'  ', prop=False)

    # If we have uses statements, we'll just add the attributes from
    # the grouping specified in each 'uses' statement
    if len(uses):
        emit_uses_attributes(ctx, stmt, uses, fd, indent+'  ')

    # Sanity checking. To be removed later
    handled = [
        'case',
        'choice',
        'container',
        'description',
        'if-feature',
        'leaf',
        'leaf-list',
        'list',
        'reference',
        'uses',
        'when'
    ]
    check_substmts(stmt, handled)


def emit_derived_from(ctx, stmt, fd, indent):

    # Sub-statements for the type statement:
    #
    # base              0..n        
    # bit               0..n        
    # enum              0..n        
    # fraction-digits   0..1        
    # length            0..1        
    # path              0..1        
    # pattern           0..n        
    # range             0..1        
    # require-instance  0..1        
    # type              0..n        

    try:
        tosca_type = ctx.type_map[stmt.arg]
    except KeyError:
        # Not a built-in type. Use type name as is, but strip local
        # prefix if necessary (since TOSCA doesn't have locally
        # defined prefixes) and prepend the tosca qualifier
        tosca_type = create_qualified_name(ctx, stmt.arg)

    # We don't have a good way to handle YANG unions. For now, just
    # write out each of the types in the union and fix manually.
    if tosca_type == 'union':
        fd.write("%s# The YANG type is a union. Select one of the following options:\n"
                 % (indent))
        types = stmt.search('type')
        count = 1
        for typedef in types:
            fd.write("%s# Option %d\n"
                     % (indent, count))
            emit_derived_from(ctx, typedef, fd, indent)
            count = count+1
        fd.write("%s#\n"
                 % (indent))
    else:
        # Regular type (not a union)
        fd.write(
            "%sderived_from: %s\n"
            % (indent, tosca_type)
        )
        # Emit commented fraction-digits
        fraction_digits = stmt.search_one("fraction-digits")
        if fraction_digits:
            emit_fraction_digits(ctx, fraction_digits, fd, indent)
        emit_constraints(ctx, stmt, fd, indent)

    handled = [
        'enum',
        'fraction-digits',
        'length',
        'range',
        'pattern',
        'type'
    ]
    check_substmts(stmt, handled)


def emit_uses_derived_from(ctx, stmt, uses, fd, indent):
    # TODO: the current code assumes that all grouping names are
    # defined at the top of the module (i.e. without a qualifier). We
    # need to handle the case where groupings are defined at lower
    # levels in the hierarchy, and need to use qualified names
    # instead.
    tosca_type = create_qualified_name(ctx, uses.arg)
    fd.write(
        "%sderived_from: %s\n"
        % (indent, tosca_type)
    )


def create_qualified_name(ctx, type_string, qualifier=None):

    # Separate on first colon
    type_parts = type_string.split(':', 1)

    # Do we have a namepace prefix?
    if (len(type_parts) == 2):
        try:
            if type_parts[0] != ctx.local_prefix:
                # prefix doesn't match local prefix. Return
                # type_string unchanged.
                return type_string
        except AttributeError:
            # No local prefix in context. Return type string
            # unchanged.
            return type_string

        # We have a localprefix. Strip it.
        type_string = type_parts[1]

    # Return qualified name for this data type
    if qualifier:
        name = qualifier + ':' + type_string
    else:
        name = type_string
    return name


def emit_units(ctx, stmt, fd, indent):
    fd.write(
        "%s# TOSCA uses scalar unit types\n"
        % indent
    )
    fd.write(
        "%s# units: %s\n"
        % (indent, stmt.arg)
    )


def emit_constraints(ctx, stmt, fd, indent):
    length = stmt.search_one('length')
    in_range = stmt.search_one('range')
    pattern = stmt.search('pattern')
    enum = stmt.search('enum')
    bits = stmt.search('bit')
    min_elements = stmt.search_one('min-elements')
    max_elements = stmt.search_one('max-elements')

    if length or in_range or len(pattern) or len(enum) \
       or min_elements or max_elements or len(bits):
        fd.write(
            "%sconstraints:\n"
            % indent
        )
        if length: 
            emit_length(ctx, length, fd, indent + '  ')
        if in_range: 
            emit_in_range(ctx, in_range, fd, indent + '  ')
        if len(pattern):
            emit_patterns(ctx, pattern, fd, indent + '  ')
        if len(enum):
            emit_enums(ctx, enum, fd, indent + '  ')
        if len(bits):
            emit_bits(ctx, bits, fd, indent + '  ')
        if min_elements: 
            emit_min_elements(ctx, min_elements, fd, indent + '  ')
        if max_elements: 
            emit_max_elements(ctx, max_elements, fd, indent + '  ')


def emit_length(ctx, stmt, fd, indent):

    # Sub-statements for the length statement:
    #
    # description    0..1        
    # error-app-tag  0..1        
    # error-message  0..1        
    # reference      0..1        

    # Parse length argument. Could include multiple ranges
    lengths = [(m[1], m[3]) for m in re_length_part.findall(stmt.arg)]

    # Do we have more then one length argument?
    if len(lengths) > 1:
        fd.write(
            "%s# This is not (yet) valid TOSCA. FIX MANUALLY\n"
            % indent
        )
        fd.write(
            "%s- or:\n"
            % indent
        )
        indent = indent + '  '
        for (low, high) in lengths:
            if high:
                if not low == 'min' and not high == 'max':
                    fd.write(
                        "%s- and:\n"
                        % indent
                    )
                    indent = indent + '  '
                if not low == 'min':
                    fd.write(
                        "%s- min_length: %s\n"
                        % (indent, low)
                    )
                if not high == 'max':
                    fd.write(
                        "%s- max_length: %s\n"
                        % (indent, high)
                    )
            else:
                if not low == 'max':
                    fd.write(
                        "%s- max_length: %s\n"
                        % (indent, low)
                    )
    else:
        (low, high) = lengths[0]
        if high:
            if not low == 'min':
                fd.write(
                    "%s- min_length: %s\n"
                    % (indent, low)
                )
            if not high == 'max':
                fd.write(
                    "%s- max_length: %s\n"
                    % (indent, high)
                )
        else:
            if not low == 'max':
                fd.write(
                    "%s- max_length: %s\n"
                    % (indent, low)
                )

    handled = []
    check_substmts(stmt, handled)


def emit_min_elements(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    fd.write(
        "%s- min_length: %s\n"
        % (indent, stmt.arg)
    )


def emit_max_elements(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    fd.write(
        "%s- max_length: %s\n"
        % (indent, stmt.arg)
    )


def emit_in_range(ctx, stmt, fd, indent):

    # Sub-statements for the range statement:
    #
    # description    0..1        
    # error-app-tag  0..1        
    # error-message  0..1        
    # reference      0..1        

    # Parse range argument. Could include multiple ranges
    ranges = [(m[1], m[6]) for m in re_range_part.findall(stmt.arg)]

    # YANG range could be list of valid values. Check first to see
    # how many of each we have.
    num_valid_values = 0
    num_ranges = 0
    for (low, high) in ranges:
        if high:
            # This is a real range
            num_ranges = num_ranges + 1
        else:
            # This is a valid value
            num_valid_values = num_valid_values + 1
            
    # Do we have both valid values and ranges, or do we have more than
    # one range argument?
    if (num_valid_values and num_ranges) or (num_ranges > 1):
        fd.write(
            "%s# This is not (yet) valid TOSCA. FIX MANUALLY\n"
            % indent
        )
        fd.write(
            "%s- or:\n"
            % indent
        )
        indent = indent + '  '

    # Write valid values:
    if num_valid_values:
        fd.write(
            "%s- valid_values:\n"
            % (indent)
        )
        for (low, high) in ranges:
            if not high:
                fd.write(
                    "%s- %s\n"
                    % (indent + '  ', str(low))
            )
        
    # Write ranges
    if num_ranges:
        for (low, high) in ranges:
            if high:
                # Update values
                if low == 'min': low = 'UNBOUNDED'
                if high == 'max': high = 'UNBOUNDED'
                fd.write(
                    "%s- in_range: [%s, %s]\n"
                    % (indent, low, high)
                )

    # All done
    handled = []
    check_substmts(stmt, handled)


def emit_patterns(ctx, stmt, fd, indent):
    for pattern in stmt:
        emit_pattern(ctx, pattern, fd, indent)


def emit_pattern(ctx, stmt, fd, indent):

    # Sub-statements for the range statement:
    #
    # description    0..1        
    # error-app-tag  0..1        
    # error-message  0..1        
    # modifier       0..1        
    # reference      0..1        
    fd.write(
        "%s- pattern: '%s'\n"
        % (indent, stmt.arg)
    )
    handled = []
    check_substmts(stmt, handled)


def emit_enums(ctx, stmt, fd, indent):
    fd.write(
        "%s- valid_values:\n"
        % indent
    )
    indent = indent + '  '
    for enum in stmt:
        emit_enum(ctx, enum, fd, indent)

def emit_enum(ctx, stmt, fd, indent):

    # Sub-statements for the enum statement:
    #
    # description   0..1        
    # if-feature    0..n        
    # reference     0..1        
    # status        0..1        
    # value         0..1        
    value = stmt.search_one('value')
    description = stmt.search_one('description')
    if must_escape(stmt.arg):
        enum = "'" + stmt.arg + "'"
    else:
        enum = stmt.arg
    if value:
        fd.write(
            "%s- %s  # Value: %s\n"
            % (indent, enum, value.arg)
        )
    else:
        fd.write(
            "%s- %s\n"
            % (indent, enum)
        )
    if description:
        lines = wrap_text(description.arg)
        for line in lines:
            fd.write(
                "%s  # %s\n"
                % (indent, line)
        )

    handled = ['value', 'description']
    check_substmts(stmt, handled)


def emit_bits(ctx, stmt, fd, indent):
    fd.write(
        "%s- valid_values:\n"
        % indent
    )
    indent = indent + '  '
    for bit in stmt:
        emit_bit(ctx, bit, fd, indent)

def emit_bit(ctx, stmt, fd, indent):
    # Sub-statements for the bit statement:
    #
    # description   0..1        
    # if-feature    0..n        
    # position      0..1        
    # reference     0..1        
    # status        0..1        
    description = stmt.search_one('description')
    if must_escape(stmt.arg):
        bit = "'" + stmt.arg + "'"
    else:
        bit = stmt.arg
    fd.write(
        "%s- %s\n"
        % (indent, bit)
    )
    if description:
        lines = wrap_text(description.arg)
        for line in lines:
            fd.write(
                "%s  # %s\n"
                % (indent, line)
        )

    handled = ['description']
    check_substmts(stmt, handled)


def must_escape(s):
    # Must escape if string represents integer
    try:
        int(s)
        return True
    except ValueError:
        pass
    # Must escape if string represents float
    try:
        float(s)
        return True
    except ValueError:
        pass
    # Must escape if string represents long
    try:
        int(s)
        return True
    except ValueError:
        pass
    # Must escape if string is boolean
    if s == 'true' or s == 'false':
        return True
    # Must escape if string is null
    if s == 'null' or s == '~':
        return True
    # Must escape if string represents date
    if timestamp_regexp.match(s):
        return True
    # No need to escape
    return False


#########################################################################    
# Generate TOSCA property definitions
#########################################################################    


def has_properties(stmt):
    """Check to see if this statement defines its own properties"""

    # First, check local property definitions
    for sub in stmt.substmts:
        if sub.keyword in ['leaf','leaf-list','list','container','choice','augment'] and \
           not is_attribute(sub): return True

    # Then, check 'uses' substatements
    usess = stmt.search('uses')
    if len(usess) > 1:
        for uses in usess[1:]:
            grouping = uses.i_grouping
            if grouping and has_properties(grouping):
                return True
    return False


def has_attributes(stmt):
    """Check to see if this statement defines its own attributes"""

    # First, check local attribute definitions
    for sub in stmt.substmts:
        if sub.keyword in ['leaf','leaf-list','list','container','choice','augment'] and \
           is_attribute(sub): return True

    # Then, check 'uses' substatements
    usess = stmt.search('uses')
    if len(usess) > 1:
        for uses in usess[1:]:
            grouping = uses.i_grouping
            if grouping and has_attributes(grouping):
                return True
            
    return False


def emit_properties(ctx, stmt, fd, indent, prop=True, qualifier=None):

    # Try to maintain the order in which properties are defined by
    # iterating over list of sub-statements
    for sub in stmt.substmts:
        if sub.keyword == 'leaf':
            emit_leaf(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        elif sub.keyword == 'leaf-list':
            emit_leaf_list(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        elif sub.keyword == 'list':
            emit_list(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        elif sub.keyword == 'container':
            emit_container(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        elif sub.keyword == 'choice':
            emit_choice(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        elif sub.keyword == 'augment':
            emit_augment(ctx, sub, fd, indent, prop=prop, qualifier=qualifier)
        else:
            # This statement does not define a property
            pass


def emit_uses_properties(ctx, stmt, uses, fd, indent):
    for use in uses:
        emit_use(ctx, stmt, use, fd, indent, prop=True)


def emit_uses_attributes(ctx, stmt, uses, fd, indent):
    for use in uses:
        emit_use(ctx, stmt, use, fd, indent, prop=False)


def emit_use(ctx, stmt, use, fd, indent, prop=True):
    # Sub-statements for the uses statement:
    #
    # augment       0..n        
    # description   0..1        
    # if-feature    0..n        
    # reference     0..1        
    # refine        0..n        
    # status        0..1        
    # when          0..1        

    grouping = use.i_grouping
    if not grouping:
        print("%s: uses(%s) not found" % (statements.mk_path_str(stmt, True), use.arg) )
        return

    if (prop and not has_properties(grouping)) or \
       (not prop and not has_attributes(grouping)):
        # Nothing to do
        return

    # Just emit the properties in this grouping. Prepend namespace
    # prefix  if necessary
    prefix = None
    type_parts = use.arg.split(':', 1)
    if (len(type_parts) == 2):
        # The name has a namespace prefix
        try:
            if type_parts[0] != ctx.local_prefix:
                # Prefix doesn't match local prefix. OK to use the
                # prefix in the name.
                prefix = type_parts[0]
        except AttributeError:
            # No local prefix in context. OK to use the prefix in the
            # name.
            prefix = type_parts[0]
    

    # Keep track of the grouping from which these properties were
    # copied.
    fd.write(
        "%s# %s from '%s'\n"
        % (indent, "properties" if prop else "attributes", use.arg)
    )
    if_feature = use.search_one('if-feature')
    if if_feature:
        fd.write(
            "%s# Used only if the '%s' feature is enabled\n"
            % (indent, if_feature.arg)
    )
    # Write property definitions
    emit_properties(ctx, use.i_grouping, fd, indent, prop=prop, qualifier=prefix)
        

def is_attribute(stmt):
    """Check if a statement defines an attribute. An attribute is a
    statement that contains a "config false" substatement.
    """
    config = stmt.search_one('config')
    return (config != None) and (config.arg=='false')


def emit_leaf(ctx, stmt, fd, indent, prop=True, qualifier=None):
    # Sub-statements for the leaf statement:
    #
    # config        0..1        
    # default       0..1        
    # description   0..1        
    # if-feature    0..n        
    # mandatory     0..1        
    # must          0..n        
    # reference     0..1        
    # status        0..1        
    # type          1           
    # units         0..1        
    # when          0..1        

    # Check if property or attribute
    is_attr = is_attribute(stmt)
    if is_attr == prop: return

    # Get name
    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg

    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)
    type = stmt.search_one('type')
    if type:
        emit_type(ctx, type, fd, indent, qualifier=qualifier)
    if not is_attr:
        mandatory = stmt.search_one('mandatory')
        emit_mandatory(ctx, mandatory, fd, indent)
    default = stmt.search_one('default')
    if default:
        emit_default(ctx, default, fd, indent)
    units = stmt.search_one('units')
    if units:
        emit_units(ctx, units, fd, indent)
    when = stmt.search_one('when')
    if when:
        emit_when(ctx, when, fd, indent)
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)

    handled = ['reference', 'description', 'type', 'units', 'config',
               'mandatory', 'default', 'must', 'when' ]
    check_substmts(stmt, handled)


def emit_mandatory(ctx, stmt, fd, indent):

    if stmt:
        required = stmt.arg
    else:
        required = 'false'
    fd.write(
        "%srequired: %s\n"
        % (indent, required)
    )


def emit_default(ctx, stmt, fd, indent):
    fd.write(
        "%sdefault: %s\n"
        % (indent, stmt.arg)
    )

def emit_commented_default(ctx, stmt, fd, indent):
    fd.write(
        "%s# TOSCA doesn't support 'default' here\n%s# default: %s\n"
        % (indent, indent, stmt.arg)
    )

def emit_when(ctx, stmt, fd, indent):
    fd.write(
        "%s# when: %s\n"
        % (indent, stmt.arg)
    )

def emit_must(ctx, stmt, fd, indent):
    # Sub-statements for the must statement:
    #
    # description    0..1        
    # error-app-tag  0..1        
    # error-message  0..1        
    # reference      0..1        
    fd.write(
        "%s# must:\n%s#   %s\n"
        % (indent, indent, stmt.arg)
    )
    error_message = stmt.search_one('error-message')
    if error_message:
        fd.write(
            "%s#   error-message: %s\n"
            % (indent, error_message.arg)
        )

    handled = ['error-message']
    check_substmts(stmt, handled)


def emit_leaf_list(ctx, stmt, fd, indent, prop=True, qualifier=None):
    # Sub-statements for the leaf-list statement:
    #
    # config        0..1        
    # default       0..n        
    # description   0..1        
    # if-feature    0..n        
    # max-elements  0..1        
    # min-elements  0..1        
    # must          0..n        
    # ordered-by    0..1        
    # reference     0..1        
    # status        0..1        
    # type          1           
    # units         0..1        
    # when          0..1        

    # Check if property or attribute
    if is_attribute(stmt) == prop: return

    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '

    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)
    fd.write(
        "%stype: list\n"
        % (indent)
    )
    type = stmt.search_one('type')
    if type:
        fd.write(
            "%sentry_schema:\n"
            % (indent)
        )
        emit_type(ctx, type, fd, indent + '  ', qualifier=qualifier)
    units = stmt.search_one('units')
    if units:
        emit_units(ctx, units, fd, indent)
    emit_constraints(ctx, stmt, fd, indent)
    when = stmt.search_one('when')
    if when:
        emit_when(ctx, when, fd, indent)
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)

    handled = ['reference', 'description', 'type', 'units', 'config',
               'min-elements', 'max-elements', 'must', 'when']
    check_substmts(stmt, handled)


def emit_list(ctx, stmt, fd, indent, prop=True, qualifier=None):

    # Sub-statements for the list statement:
    #
    # action        0..n        
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # config        0..1        
    # container     0..n        
    # description   0..1        
    # grouping      0..n        
    # if-feature    0..n        
    # key           0..1        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # max-elements  0..1        
    # min-elements  0..1        
    # must          0..n        
    # notification  0..n        
    # ordered-by    0..1        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    # unique        0..n        
    # uses          0..n        
    # when          0..1        

    # Check if property or attribute
    if is_attribute(stmt) == prop: return

    # Find qualified entry schema for this container. If the container
    # statement has a single 'uses' statement only, we use the name of
    # the grouping to which that 'uses' statement refers.
    if has_single_uses_stmt_only(stmt):
        entry_schema = get_single_uses_stmt_grouping(ctx, stmt)
    else:
        entry_schema = stmt.arg
    if qualifier:
        entry_schema = qualifier + ':' + entry_schema

    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)
    fd.write(
        "%stype: list\n"
        % (indent)
    )
    fd.write(
        "%sentry_schema: %s\n"
        % (indent, entry_schema)
    )
    emit_constraints(ctx, stmt, fd, indent)
    # Emit commented key
    key = stmt.search_one('key')
    if key:
        emit_key(ctx, key, fd, indent)
    # Emit commented unique
    unique = stmt.search_one('unique')
    if unique:
        emit_unique(ctx, unique, fd, indent)
    # Emit commented ordered_by
    ordered_by = stmt.search_one('ordered-by')
    if ordered_by:
        emit_ordered_by(ctx, ordered_by, fd, indent)

    handled = ['reference', 'description', 'config', 'ordered-by',
               'typedef', 'container', 'grouping', 'list', 'uses', 'key', 'unique',
               'leaf', 'leaf-list', 'min-elements', 'max-elements', 'when', 'must']
    check_substmts(stmt, handled)


def emit_if_feature(ctx, stmt, fd, indent):
    fd.write(
        "%s# if-feature: %s\n"
        % (indent, stmt.arg)
    )


def emit_key(ctx, stmt, fd, indent):
    fd.write(
        "%s# key: %s\n"
        % (indent, stmt.arg)
    )


def emit_ordered_by(ctx, stmt, fd, indent):
    fd.write(
        "%s# ordered-by: %s\n"
        % (indent, stmt.arg)
    )


def emit_container(ctx, stmt, fd, indent, prop=True, qualifier=None):

    # Sub-statements for the container statement:
    #
    # action        0..n        
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # config        0..1        
    # container     0..n        
    # description   0..1        
    # grouping      0..n        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # must          0..n        
    # notification  0..n        
    # presence      0..1        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    # uses          0..n        
    # when          0..1        

    # Check if property or attribute
    if is_attribute(stmt) == prop: return

    # Find qualified type name for this container. If the container
    # statement has a single 'uses' statement only, we use the name of
    # the grouping to which that 'uses' statement refers.
    if has_single_uses_stmt_only(stmt):
        type_name = get_single_uses_stmt_grouping(ctx, stmt)
    else:
        type_name = stmt.arg
    if qualifier:
        type_name = qualifier + ':' + type_name

    # Property name
    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)
    fd.write(
        "%stype: %s\n"
        % (indent, type_name)
    )
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)
    presence = stmt.search_one('presence')
    if presence:
        emit_presence(ctx, presence, fd, indent)

    handled = ['reference', 'description', 'config', 'presence',
               'typedef', 'container', 'grouping', 'list', 'uses',
               'leaf', 'leaf-list', 'when', 'must']
    check_substmts(stmt, handled)


def emit_choice(ctx, stmt, fd, indent, prop=True, qualifier=None):
    # Sub-statements for the choice statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # case          0..n        
    # choice        0..n        
    # config        0..1        
    # container     0..n        
    # default       0..1        
    # description   0..1        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # mandatory     0..1        
    # reference     0..1        
    # status        0..1        
    # when          0..1        

    # Check if property or attribute
    is_attr = is_attribute(stmt)
    if is_attr == prop: return

    # Get list of cases or list of leafs. If we have a list of leafs,
    # each leaf is equivalate to a case with a single leaf node.
    cases = stmt.search('case')
    leafs = stmt.search('leaf')
    if len(cases):
        options = cases
    elif len(leafs):
        options = leafs
    else:
        options = list()

    # Define a property for the choice
    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    orig_indent = indent
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    # Choices are always strings
    fd.write(
        "%stype: string\n"
        % (indent)
    )
    if not is_attr:
        mandatory = stmt.search_one('mandatory')
        emit_mandatory(ctx, mandatory, fd, indent)
    default = stmt.search_one('default')
    if default:
        emit_default(ctx, default, fd, indent)
    # Write valid values
    fd.write(
        "%sconstraints:\n"
        % (indent)
    )
    indent = indent + '  '
    fd.write(
        "%s- valid_values:\n"
        % (indent)
    )
    indent = indent + '  '
    for option in options:
        fd.write(
            "%s- %s\n"
            % (indent, option.arg)
        )
        
    # Define properties for each of the options.
    indent = orig_indent
    fd.write(
        "%s# Select one of the following options\n%s#\n"
        % (indent, indent)
    )
    for case in cases:
        emit_case(ctx, case, fd, indent, qualifier=qualifier)
    # Emit leafs if we don't have an explicit list of cases
    for leaf in leafs:
        # Add descriptive commentary 
        fd.write(
            "%s# The following properties are used in case of '%s'\n"
            % (indent, leaf.arg)
        )
        emit_leaf(ctx, leaf, fd, indent, qualifier=qualifier)
    fd.write(
        "%s# End of options\n%s#\n"
        % (indent, indent)
    )

    handled = ['case', 'config', 'default', 'description', 'leaf', 'mandatory' ]
    check_substmts(stmt, handled)


def emit_case(ctx, stmt, fd, indent, qualifier=None):
    # Sub-statements for the case statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # container     0..n        
    # description   0..1        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # reference     0..1        
    # status        0..1        
    # uses          0..n        
    # when          0..1        

    # Add descriptive commentary 
    fd.write(
        "%s# The following properties are used in case of '%s'\n"
        % (indent, stmt.arg)
    )
    description = stmt.search_one('description')
    if description:
        lines = wrap_text(description.arg)
        for line in lines:
            fd.write(
                "%s  # %s\n"
                % (indent, line)
        )
    # Continue emitting properties
    emit_properties(ctx, stmt, fd, indent, qualifier=qualifier)

    handled = ['leaf', 'leaf-list', 'list', 'container', 'choice', 'description' ]
    check_substmts(stmt, handled)


def emit_type(ctx, stmt, fd, indent, qualifier=None):

    # Sub-statements for the type statement:
    #
    # base              0..n        
    # bit               0..n        
    # enum              0..n        
    # fraction-digits   0..1        
    # length            0..1        
    # path              0..1        
    # pattern           0..n        
    # range             0..1        
    # require-instance  0..1        
    # type              0..n        

    try:
        tosca_type = ctx.type_map[stmt.arg]
    except KeyError:
        # Not a built-in type. Use type name as is, but strip local
        # prefix if necessary (since TOSCA doesn't have locally
        # defined prefixes) and prepend tosca qualifier
        tosca_type = create_qualified_name(ctx, stmt.arg, qualifier=qualifier)

    # We don't have a good way to handle YANG unions. For now, just
    # write out each of the types in the union and fix manually.
    if tosca_type == 'union':
        fd.write("%s# The YANG type is a union. Select one of the following options:\n"
                 % (indent))
        types = stmt.search('type')
        count = 1
        for typedef in types:
            fd.write("%s# Option %d\n"
                     % (indent, count))
            emit_type(ctx, typedef, fd, indent)
            count = count+1
        fd.write("%s#\n"
                 % (indent))
    else:
        # Regular type (not a union)
        fd.write(
            "%stype: %s\n"
            % (indent, tosca_type)
        )
        # For leafrefs, emit path for reference
        path = stmt.search_one("path")
        if path:
            emit_path(ctx, path, fd, indent)
        # Emit commented fraction-digits
        fraction_digits = stmt.search_one("fraction-digits")
        if fraction_digits:
            emit_fraction_digits(ctx, fraction_digits, fd, indent)
        emit_constraints(ctx, stmt, fd, indent)

    handled = ['bit', 'enum', 'fraction-digits', 'length', 'range', 'pattern', 'path', 'type']
    check_substmts(stmt, handled)


def emit_presence(ctx, stmt, fd, indent):
    fd.write(
        "%s# presence: %s\n"
        % (indent, stmt.arg)
    )

def emit_path(ctx, stmt, fd, indent):
    fd.write(
        "%s# path: %s\n"
        % (indent, stmt.arg)
    )
    
def emit_fraction_digits(ctx, stmt, fd, indent):
    fd.write(
        "%s# fraction-digits: %s\n"
        % (indent, stmt.arg)
    )
    
def  emit_unique(ctx, stmt, fd, indent):
    fd.write(
        "%s# unique: %s\n"
        % (indent, stmt.arg)
    )

def    emit_augment(ctx, stmt, fd, indent, prop=True):
    # Sub-statements for the augment statement:
    #
    # action        0..n        
    # anydata       0..n        
    # anyxml        0..n        
    # case          0..n        
    # choice        0..n        
    # container     0..n        
    # description   0..1        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # notification  0..n        
    # reference     0..1        
    # status        0..1        
    # uses          0..n        
    # when          0..1        

    # Find qualified type name for this augment
    type_name = stmt.arg

    if ctx.opts.camel_case:
        name = stringcase.camelcase(stmt.arg)
    else:
        name = stmt.arg
    fd.write(
        "%s%s:\n"
        % (indent, name)
    )
    indent = indent + '  '
    description = stmt.search_one('description')
    if description:
        emit_description(ctx, description, fd, indent)
    emit_metadata(ctx, stmt, fd, indent)
    fd.write(
        "%stype: %s\n"
        % (indent, type_name)
    )
    must = stmt.search_one('must')
    if must:
        emit_must(ctx, must, fd, indent)

    handled = ['reference', 'description', 
               'container', 'list', 'uses',
               'leaf', 'leaf-list', 'when', 'must']
    check_substmts(stmt, handled)


def    emit_submodule(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # augment       0..n        
    # belongs-to    1           
    # choice        0..n        
    # contact       0..1        
    # container     0..n        
    # description   0..1        
    # deviation     0..n        
    # extension     0..n        
    # feature       0..n        
    # grouping      0..n        
    # identity      0..n        
    # import        0..n        
    # include       0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # notification  0..n        
    # organization  0..1        
    # reference     0..1        
    # revision      0..n        
    # rpc           0..n        
    # typedef       0..n        
    # uses          0..n        
    # yang-version  1           
    print('submodule')

def    emit_include(ctx, stmt, fd, indent):

    # Sub-statements for the includestatement:
    #
    # description    0..1        
    # reference      0..1        
    # revision-date  0..1        
    print('include')

def    emit_revision_date(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('revision-date')

def    emit_extension(ctx, stmt, fd, indent):
    # Sub-statements for the extension statement:
    #
    # argument      0..1        
    # description   0..1        
    # reference     0..1        
    # status        0..1        
    print('extension')

def    emit_argument(ctx, stmt, fd, indent):
    # Sub-statements for the argumement statement:
    #
    # yin-element   0..1        
    print('argument')

def    emit_yin_element(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('yin-element')

def    emit_identity(ctx, stmt, fd, indent):
    # Sub-statements for the identity statement:
    #
    # base          0..n        
    # description   0..1        
    # if-feature    0..n        
    # reference     0..1        
    # status        0..1        
    print('identity')

def    emit_base(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('base')

def    emit_require_instance(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('require-instance')

def    emit_position(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('position')

def    emit_status(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('status')

def    emit_config(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('config')

def    emit_error_message(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('error-message')

def    emit_error_app_tag(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('error-app-tag')

def    emit_value(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('value')

def    emit_modifier(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('modifier')

def    emit_anydata(ctx, stmt, fd, indent):
    # Sub-statements for the anydata statement:
    #
    # config        0..1        
    # description   0..1        
    # if-feature    0..n        
    # mandatory     0..1        
    # must          0..n        
    # reference     0..1        
    # status        0..1        
    # when          0..1        
    print('anydata')

def    emit_anyxml(ctx, stmt, fd, indent):
    # Sub-statements for the anyxml statement:
    #
    # config        0..1        
    # description   0..1        
    # if-feature    0..n        
    # mandatory     0..1        
    # must          0..n        
    # reference     0..1        
    # status        0..1        
    # when          0..1        
    print('anyxml')

def    emit_refine(ctx, stmt, fd, indent):
    # Sub-statements for the module statement:
    #
    print('refine')

def    emit_rpc(ctx, stmt, fd, indent):
    # Sub-statements for the rpc statement:
    #
    # description   0..1        
    # grouping      0..n        
    # if-feature    0..n        
    # input         0..1        
    # output        0..1        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    print('rpc')

def    emit_action(ctx, stmt, fd, indent):
    # Sub-statements for the action statement:
    #
    # description   0..1        
    # grouping      0..n        
    # if-feature    0..n        
    # input         0..1        
    # output        0..1        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    print('action')

def    emit_input(ctx, stmt, fd, indent):
    # Sub-statements for the input statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # container     0..n        
    # grouping      0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # must          0..n        
    # typedef       0..n        
    # uses          0..n        
    print('input')

def    emit_output(ctx, stmt, fd, indent):
    # Sub-statements for the output statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # container     0..n        
    # grouping      0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # must          0..n        
    # typedef       0..n        
    # uses          0..n        
    print('output')

def    emit_notification(ctx, stmt, fd, indent):
    # Sub-statements for the notification statement:
    #
    # anydata       0..n        
    # anyxml        0..n        
    # choice        0..n        
    # container     0..n        
    # description   0..1        
    # grouping      0..n        
    # if-feature    0..n        
    # leaf          0..n        
    # leaf-list     0..n        
    # list          0..n        
    # must          0..n        
    # reference     0..1        
    # status        0..1        
    # typedef       0..n        
    # uses          0..n        
    print('notification')

def    emit_deviation(ctx, stmt, fd, indent):
    # Sub-statements for the deviation statement:
    #
    # description   0..1        
    # deviate       1..n        
    # reference     0..1        
    print('deviation')

def    emit_deviate(ctx, stmt, fd, indent):
    # Sub-statements for the deviate statement:
    #
    # config        0..1        
    # default       0..n        
    # mandatory     0..1        
    # max-elements  0..1        
    # min-elements  0..1        
    # must          0..n        
    # type          0..1        
    # unique        0..n        
    # units         0..1        
    print('deviate')

# Debugging support: print unhandled substatements for a given
# statement.
def check_substmts(stmt, handled):
    for sub in stmt.substmts:
        if not sub.keyword in handled:
            if stmt.keyword in  ['module', 'submodule']:
                warning = "/: %s(%s) not handled" % (
                    sub.keyword, sub.arg
                )
            else:
                warning = "%s: %s(%s) not handled" % (
                    statements.mk_path_str(stmt, True), sub.keyword, sub.arg
                )
            print(warning)


# Debugging support: print a YANG statement            
def print_statement(stmt):
    for key in dir(stmt):
        try:
            print(key + " = " + str(getattr(stmt, key)))
        except AttributeError:
            pass
        
