#!/usr/bin/env python3
import json
import re
from pathlib import Path

from xmlschema import XMLSchema
from xmlschema.validators.wildcards import XsdAnyElement, XsdAnyAttribute
from flask import Flask, abort, current_app, g, render_template
from flask_frozen import Freezer
from markupsafe import Markup, escape

from featurekatalog import all_restriktioner, parse_featurekatalog
from wrapper import SchemaEx

ROOT = Path(__file__).parent
VERSIONS_DIR = ROOT / 'versions'
ERRORCODES_PATH = ROOT / 'errorcodes.json'

# Newest first - used as the display order on the version landing page.
VERSIONS = {
    '2.2.0': '2.2_ler.xsd',
    '2.1.0': '2.1_ler.xsd',
    '2.0.1': '2.0_ler.xsd',
    '2.0.0': '2.0_ler.xsd',
}
LATEST_VERSION = '2.2.0'

GML_ABSTRACT_TYPE = '{http://www.opengis.net/gml/3.2}AbstractGMLType'

# 2.2_ler.xsd imports both of these (LinearDimension, LinearAnnotation, TextAnnotation
# live here, not in the LER namespace itself) - schema.elements only holds ler.xsd's own
# namespace, so these three otherwise silently disappear from every XSD-derived page.
LER_FAMILY_NAMESPACES = {
    'http://data.gov.dk/schemas/LER/2/gml',
    'http://data.gov.dk/schemas/dimensions/2/gml',
    'http://data.gov.dk/schemas/annotations/2/gml',
}

# External standards (GML, ISO 19139/gmx, Dublin Core) are vendored once under
# schemas/http|https/, shared across every LER version. 2.2.0's own XSD already
# references them via relative paths into that vendored tree; 2.0.0/2.0.1/2.1.0's
# XSDs reference the same namespaces via absolute ler.dk-external URLs instead.
# Passing this uniformly for every version resolves both cases against the local
# vendored copies, so loading a schema never depends on a live network fetch.
EXTERNAL_LOCATIONS = [
    ('http://www.opengis.net/gml/3.2', str(ROOT / 'schemas/http/schemas.opengis.net/gml/3.2.1/gml.xsd')),
    ('http://www.isotc211.org/2005/gmx', str(ROOT / 'schemas/https/schemas.isotc211.org/19139/-/gmx/1.0/gmx.xsd')),
    ('http://purl.org/dc/terms/', str(ROOT / 'schemas/https/www.dublincore.org/schemas/xmls/qdc/2008/02/11/dcterms.xsd')),
]


def normalize_navn(navn):
    """ASCII-fold Danish names the same way the XSD's element names do
    (æ/ø/å -> ae/oe/aa), so docx-navne and XSD-elementnavne can be matched."""
    return navn.lower().replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa')

app = Flask(__name__)
app.config['FREEZER_DESTINATION'] = str(ROOT / 'docs')
app.config['FREEZER_RELATIVE_URLS'] = True
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

_featuretyper = {}
_schex = {}
_type_tree = {}
_chains = {}
_xsdelement_details = {}
_errorcodes = None


def get_featuretyper(version):
    if version not in _featuretyper:
        docx_path = VERSIONS_DIR / version / 'ler_featurekatalog.docx'
        _featuretyper[version] = parse_featurekatalog(str(docx_path))
    return _featuretyper[version]


def get_schex(version):
    if version not in _schex:
        xsd_path = VERSIONS_DIR / version / 'schemas' / VERSIONS[version]
        schex = SchemaEx(XMLSchema(str(xsd_path), locations=EXTERNAL_LOCATIONS))
        # SchemaEx's own type-hierarchy walk (built in __init__) only seeds from
        # schex.schema.elements (ler.xsd's own namespace). Extend it with every
        # element in the imported dimensions/annotations namespaces too, so Type
        # Tree/Type Chains cover them as well. _register_type_and_ancestors is
        # idempotent for already-registered types, so re-running it for the ler.xsd
        # elements too is harmless.
        for elm in schex.schema.maps.elements.values():
            if elm.target_namespace in LER_FAMILY_NAMESPACES:
                schex._register_type_and_ancestors(elm.type)
        _schex[version] = schex
    return _schex[version]


def get_all_xsd_elements(version):
    """Every element across LER + Dimensions + Annotations (not just ler.xsd's own
    namespace) - these are what the featurekatalog docx calls featuretyper."""
    schex = get_schex(version)
    return [
        elm for elm in schex.schema.maps.elements.values()
        if elm.target_namespace in LER_FAMILY_NAMESPACES
    ]


def get_xsd_element_by_navn(version, navn):
    target = normalize_navn(navn)
    for elm in get_all_xsd_elements(version):
        if normalize_navn(elm.local_name) == target:
            return elm
    return None


def _own_content_group(xsd_type):
    """The XsdGroup holding xsd_type's own (non-inherited) content - the last item of
    xsd_type.content if it has a base type, or the whole content if it's a root type."""
    if not xsd_type.content:
        return None
    return xsd_type.content[-1] if xsd_type.derivation == 'extension' else xsd_type.content


def _has_choice(group):
    """True if an xs:choice appears anywhere in group, at any nesting depth."""
    if group.model == 'choice':
        return True
    return any(hasattr(item, 'model') and _has_choice(item) for item in group)


def _assert_own_content_is_flat(xsd_type):
    """The 'Elementer defineret direkte på denne type' table on xsdtype_details.html
    lists a type's own elements as a plain AND-list - that's only accurate because
    every type's own content in the current XSD happens to be choice-free (verified
    2.2_ler.xsd has none). If a future XSD swap introduces an xs:choice into some
    type's own content, that table would silently misrepresent 'either/or' as
    'all required'. Fail loudly at build time instead, so this gets caught and the
    display gets redesigned before the site ships with wrong-looking data."""
    own = _own_content_group(xsd_type)
    if own is not None and _has_choice(own):
        raise RuntimeError(
            f"{xsd_type.prefixed_name}'s own content contains an xs:choice - the flat "
            "'Elementer defineret direkte på denne type' table (xsdtype_details.html) no "
            "longer accurately represents it. The display needs to be redesigned to show "
            "choice/alternatives before the site can be rebuilt."
        )


def _assert_derivation_is_extension_or_root(xsd_type):
    """_own_content_group() only knows how to isolate 'this type's own elements' for two
    cases: derivation='extension' (own = content[-1]) or a root type with no base
    (derivation=None, own = the whole content). It has never been tested against
    derivation='restriction' (verified: 0 of the 31 relevant types currently use it -
    all are 'extension' or root). Restriction narrows a base's content rather than
    adding to it, so content[-1] would not mean 'own elements' for such a type - the
    whole 'defineret direkte'/'defining type' analysis would silently mislabel it.
    Fail loudly at build time instead."""
    if xsd_type.derivation not in ('extension', None):
        raise RuntimeError(
            f"{xsd_type.prefixed_name} has derivation={xsd_type.derivation!r} - "
            "_own_content_group() only handles 'extension' and root types. The "
            "'own elements' logic needs to be redesigned for restriction before the "
            "site can be rebuilt."
        )


def _assert_not_mixed_content(xsd_type):
    """The element tables (xsdelement_details.html, xsdtype_details.html) list only
    structured child elements - they say nothing about free text. If a type has
    mixed="true" content, arbitrary text can appear between/around those elements too,
    which none of the tables would mention (verified: 0 of the 31 relevant types are
    mixed). Fail loudly at build time instead of silently omitting that."""
    if getattr(xsd_type, 'mixed', False):
        raise RuntimeError(
            f'{xsd_type.prefixed_name} has mixed content (mixed="true") - the element '
            "tables don't account for interspersed free text. This needs to be shown "
            "somehow before the site can be rebuilt."
        )


def _has_wildcard(group):
    """True if an xs:any wildcard particle appears anywhere in group, at any nesting depth."""
    for item in group:
        if hasattr(item, 'model'):
            if _has_wildcard(item):
                return True
        elif isinstance(item, XsdAnyElement):
            return True
    return False


def _assert_no_wildcards(xsd_type):
    """The element/attribute tables list only named, declared elements and attributes -
    an xs:any or xs:anyAttribute wildcard would mean 'and also anything else from
    [namespace] is allowed here', which none of the tables mention (verified: 0 of the
    31 relevant types have either). Worse than a display gap: xmlschema's
    content.iter_elements() does NOT filter out xs:any particles (confirmed by testing),
    so an XsdAnyElement would flow straight into describe_xsd_element_type() and the
    templates' elm.prefixed_name/elm.occurs accesses, which are written assuming a real
    XsdElement - likely to raise, not just mislead. Fail loudly and clearly here
    instead of an obscure AttributeError deep in template rendering."""
    own = _own_content_group(xsd_type)
    if own is not None and _has_wildcard(own):
        raise RuntimeError(
            f"{xsd_type.prefixed_name}'s own content contains an xs:any wildcard - the "
            "element tables assume real XsdElements (elm.prefixed_name, elm.occurs, ...) "
            "and don't handle XsdAnyElement. This needs to be redesigned before the site "
            "can be rebuilt."
        )
    if xsd_type.is_complex() and xsd_type.attributes is not None:
        if any(isinstance(v, XsdAnyAttribute) for v in xsd_type.attributes.values()):
            raise RuntimeError(
                f"{xsd_type.prefixed_name} has an xs:anyAttribute wildcard - the "
                "'[attrs: ...]' listing in describe_xsd_element_type() only handles "
                "named attributes. This needs to be shown somehow before the site can "
                "be rebuilt."
            )


def _assert_no_abstract_elements(xsd_type):
    """An element declared abstract="true" can never literally appear in an XML
    instance - only substitutes (via substitutionGroup) can. If the own-elements tables
    ever list an abstract element as a normal required/optional entry, that's actively
    misleading (verified: 0 of the 31 relevant types have one in their own content).
    Fail loudly rather than silently show it as if it were directly usable."""
    own = _own_content_group(xsd_type)
    if own is None:
        return
    for elm in own.iter_elements():
        if getattr(elm, 'abstract', False):
            raise RuntimeError(
                f"{xsd_type.prefixed_name} has an abstract element ({elm.prefixed_name}) "
                "in its own content - the element tables show it as a normal entry, "
                "which is misleading since it can never appear directly, only via "
                "substitutionGroup members. This needs to be shown somehow before the "
                "site can be rebuilt."
            )


XSD_NAMESPACE = 'http://www.w3.org/2001/XMLSchema'


def _describe_simple_type(xsd_simple_type):
    """Human-readable name + constraints for a simple type: union members joined with
    'eller', or the type's name plus any facets it declares itself (maxLength,
    enumeration, pattern, ...). Facets on the XSD-namespace's own built-in types (eg.
    xs:double's internal lexical-space pattern) are skipped - those aren't constraints
    LER's schema authors added, they're inherent to the primitive itself."""
    if getattr(xsd_simple_type, 'member_types', None):
        return ' eller '.join(_describe_simple_type(m) for m in xsd_simple_type.member_types)
    name = xsd_simple_type.prefixed_name or '(anonym)'
    if xsd_simple_type.target_namespace == XSD_NAMESPACE:
        return name
    parts = [name]
    for tag, facet in (xsd_simple_type.facets or {}).items():
        local_tag = tag.split('}')[-1] if isinstance(tag, str) else str(tag)
        if getattr(facet, 'enumeration', None):
            parts.append(f'{local_tag}=' + '|'.join(facet.enumeration))
        elif getattr(facet, 'regexps', None):
            parts.append(f'{local_tag}=' + '|'.join(facet.regexps))
        elif getattr(facet, 'value', None) is not None:
            parts.append(f'{local_tag}={facet.value}')
    return '; '.join(parts)


@app.template_filter('describe_type')
def describe_xsd_element_type(elm):
    """Human-readable description of an element's type and its constraints - handles
    plain simple types, unions (eg. kodeliste + 'andet: ...'-pattern), and complex types
    with simple content (eg. GML's value+uom 'measure' pattern), by introspecting the
    compiled xmlschema type/facet objects. Verified against every own-defined element
    across the whole relevant type hierarchy without errors."""
    xsd_type = elm.type
    if xsd_type.is_simple():
        return _describe_simple_type(xsd_type)
    if xsd_type.content_type_label == 'simple':
        description = _describe_simple_type(xsd_type.content)
        attr_descriptions = []
        for a in (xsd_type.attributes or {}).values():
            if not a.prefixed_name:
                continue
            label = a.prefixed_name
            if a.use == 'required':
                label += ' (required)'
            attr_descriptions.append(label)
        if attr_descriptions:
            description += ' [attrs: ' + ', '.join(attr_descriptions) + ']'
        return description
    return xsd_type.prefixed_name or '(anonym, element content)'


def get_type_tree(version):
    """List of (depth, xsdtype), walking the type hierarchy from AbstractGMLType down,
    filtered to only the types actually used by a featurekatalog featuretype (ie. the
    same featuretyper documented in the docx) plus their ancestor types (eg.
    AbstractGMLType/AbstractFeatureType themselves, which no element uses directly but
    which every used type descends from) - not the other XSD-only types (kodelister,
    PropertyType wrappers, ...) that never appear in the docx."""
    if version not in _type_tree:
        schex = get_schex(version)
        absgmltype = schex.maps.types[GML_ABSTRACT_TYPE]
        known_types = {elm.type for elm in get_all_xsd_elements(version)}
        relevant_types = known_types | {
            ancestor
            for known_type in known_types
            for ancestor in schex.iter_type_ancestors(known_type)
        }
        tree = [
            (depth, xsdtype)
            for depth, xsdtype in schex.walk_type_hierarchy(absgmltype)
            if xsdtype in relevant_types
        ]
        for _depth, xsdtype in tree:
            _assert_own_content_is_flat(xsdtype)
            _assert_derivation_is_extension_or_root(xsdtype)
            _assert_not_mixed_content(xsdtype)
            _assert_no_wildcards(xsdtype)
            _assert_no_abstract_elements(xsdtype)
        _type_tree[version] = tree
    return _type_tree[version]


def get_chains(version):
    """List of (xsdtype, [ancestors..., xsdtype]) for every type in the tree."""
    if version not in _chains:
        schex = get_schex(version)
        chains = []
        for _depth, xsdtype in get_type_tree(version):
            chain = [xsdtype] + list(schex.iter_type_ancestors(xsdtype))
            chain.reverse()
            chains.append((xsdtype, chain))
        _chains[version] = chains
    return _chains[version]


def get_element_defining_types(version, xsd_type):
    """Dict of {sub-element prefixed_name: xsd_type} mapping every element allowed by
    xsd_type's content model to the type - xsd_type itself, or one of its ancestors -
    that actually introduces it. xsd_type.content already includes inherited elements
    flattened in, so without walking the ancestor chain there's no way to tell which
    level of the inheritance chain originally declares a given element."""
    schex = get_schex(version)
    chain = [xsd_type] + list(schex.iter_type_ancestors(xsd_type))
    chain.reverse()
    defining_type = {}
    for t in chain:
        for e in t.content.iter_elements():
            if e.prefixed_name not in defining_type:
                defining_type[e.prefixed_name] = t
    return defining_type


def get_xsdelement_details(version):
    """List of {'elm': element, 'allowed_elms': [children...]} for every schema element."""
    if version not in _xsdelement_details:
        _xsdelement_details[version] = [
            {'elm': elm, 'allowed_elms': list(elm.iterchildren())}
            for elm in get_all_xsd_elements(version)
        ]
    return _xsdelement_details[version]


NUMBERED_ERRORCODE = re.compile(r'^\d\d-\d+$')


def get_errorcodes():
    """(numeric_groups, named_rules), from errorcodes.json (see fetch_errorcodes.py).
    LER's /api/errorcodes returns one flat list mixing two things that behave
    differently in an API response: numbered codes (StatusCode like '13-300') that
    actually appear as Error.ErrorCode, and named business rules (StatusCode like
    'Check3DGeometryRule') that only ever show up as free text inside
    Error.PrettyErrorMessage, with ErrorCode staying the generic code of the
    rejecting service. numeric_groups is [(prefix, [codes...]), ...] sorted by
    prefix, e.g. ('13', [...]) for all 13-xxx codes."""
    global _errorcodes
    if _errorcodes is None:
        codes = json.loads(ERRORCODES_PATH.read_text())
        numeric = [c for c in codes if NUMBERED_ERRORCODE.match(c['StatusCode'])]
        named = sorted(
            (c for c in codes if not NUMBERED_ERRORCODE.match(c['StatusCode'])),
            key=lambda c: c['StatusCode'],
        )
        groups = {}
        for c in numeric:
            groups.setdefault(c['StatusCode'].split('-')[0], []).append(c)
        numeric_groups = [(prefix, groups[prefix]) for prefix in sorted(groups)]
        _errorcodes = (numeric_groups, named)
    return _errorcodes


@app.template_filter('anchor')
def anchor_filter(prefixed_name):
    return prefixed_name.lower().replace(':', '-')


def get_by_navn(version, navn):
    for ft in get_featuretyper(version):
        if ft['navn'] == navn:
            return ft
    return None


def get_xsdelement_detail_by_slug(version, slug):
    for elmdict in get_xsdelement_details(version):
        if anchor_filter(elmdict['elm'].prefixed_name) == slug:
            return elmdict
    return None


def get_chain_by_slug(version, slug):
    for xsdtype, chain in get_chains(version):
        if anchor_filter(xsdtype.prefixed_name) == slug:
            return xsdtype, chain
    return None


@app.template_filter('linkify')
def linkify_filter(value):
    """Turn values like 'Ledning (Featuretype)' or plain 'Ledning' into a link,
    if 'Ledning' is a known featuretype."""
    if not isinstance(value, str):
        return value
    known_names = {ft['navn'] for ft in get_featuretyper(g.version)}
    match = re.match(r'^(.*?)(\s\(\w+\))?$', value, re.DOTALL)
    name, suffix = match.group(1), match.group(2) or ''
    if name in known_names:
        # Use the (possibly Frozen-Flask-patched, relative-URL-producing) url_for
        # from the Jinja globals, not flask.url_for directly - see freezer.register_generator
        # note in Frozen-Flask docs: relative_url_for only patches app.jinja_env.globals.
        jinja_url_for = current_app.jinja_env.globals['url_for']
        return Markup('<a href="{}">{}</a>{}').format(jinja_url_for('docx_details', navn=name), name, suffix)
    return escape(value)


## VERSION-PREFIXED ROUTING
##
## Every route below except the bare '/' takes a leading /<version>/ segment.
## url_value_preprocessor/url_defaults make this transparent to templates: every
## existing url_for(...) call keeps working unmodified, automatically picking up
## whichever version the current page belongs to.


@app.url_value_preprocessor
def pull_version(endpoint, values):
    if values is not None and 'version' in values:
        g.version = values['version']


@app.url_defaults
def add_version(endpoint, values):
    if 'version' in values or getattr(g, 'version', None) is None:
        return
    if current_app.url_map.is_endpoint_expecting(endpoint, 'version'):
        values['version'] = g.version


## FORSIDE (unprefixed - the site's actual front page, lists the versions)


@app.route('/')
def forside():
    return render_template('forside.html', versions=VERSIONS, latest_version=LATEST_VERSION)


## FEJLKODER (unprefixed - identical across every LER/featurekatalog version, see
## adr/901-ler-api-error-codes.md. Unlike XSD/docx-derived content, LER's error codes
## API isn't versioned alongside the schema, so there's nothing to duplicate per version.
## errorcodes.html is standalone like forside.html (doesn't extend base.html) - it has no
## g.version of its own, so it can't build version-dependent nav links like the other pages.)


@app.route('/errorcodes/')
def errorcodes():
    numeric_groups, named = get_errorcodes()
    return render_template('errorcodes.html', numeric_groups=numeric_groups, named=named)


## OVERVIEW PAGES (list like)


@app.route('/<version>/')
def index(version):
    return render_template('index.html')


@app.route('/<version>/featuretype_list/')
def featuretype_list(version):
    grupper = {}
    for ft in get_featuretyper(version):
        ft = dict(ft)
        ft['xsd_elm'] = get_xsd_element_by_navn(version, ft['navn'])
        grupper.setdefault(ft['pakke'], []).append(ft)
    return render_template('featuretype_list.html', grupper=grupper.items())


@app.route('/<version>/featuretype_tree/')
def featuretype_tree(version):
    return render_template('featuretype_tree.html', absgmltype_tree=get_type_tree(version))


@app.route('/<version>/restriktioner/')
def restriktioner(version):
    return render_template('restriktioner.html', restriktioner=all_restriktioner(get_featuretyper(version)))


@app.route('/<version>/general_constraints/')
def general_constraints(version):
    return render_template('general_constraints.html')


## SUMMARY PAGE (cross-source overview of a single feature type)


@app.route('/<version>/featuretype_summary/<navn>/')
def featuretype_summary(version, navn):
    ft = get_by_navn(version, navn)
    if ft is None:
        abort(404)
    return render_template('featuretype_summary.html', ft=ft, xsd_elm=get_xsd_element_by_navn(version, navn))


## DETAILS PAGES (for individual feature types, xsd elemenets or xsd types)


@app.route('/<version>/docx_details/<navn>/')
def docx_details(version, navn):
    ft = get_by_navn(version, navn)
    if ft is None:
        abort(404)
    return render_template('docx_details.html', ft=ft)


@app.route('/<version>/xsdelement_details/<slug>/')
def xsdelement_details(version, slug):
    elmdict = get_xsdelement_detail_by_slug(version, slug)
    if elmdict is None:
        abort(404)
    return render_template('xsdelement_details.html', elmdict=elmdict)


@app.route('/<version>/xsdtype_details/<slug>/')
def xsdtype_details(version, slug):
    result = get_chain_by_slug(version, slug)
    if result is None:
        abort(404)
    xsdtype, chain = result
    defining_types = get_element_defining_types(version, xsdtype)
    own_elements = {t: [] for t in chain}
    for name, defining_type in defining_types.items():
        own_elements[defining_type].append(name)
    for names in own_elements.values():
        names.sort()
    own_elm_objs = [e for e in xsdtype.content.iter_elements() if defining_types[e.prefixed_name] is xsdtype]
    return render_template(
        'xsdtype_details.html',
        xsdtype=xsdtype,
        chain=chain,
        own_elements=own_elements,
        own_elm_objs=own_elm_objs,
    )


## FREEZER (static site generation)


freezer = Freezer(app)


@freezer.register_generator
def forside_urls():
    yield 'forside', {}


@freezer.register_generator
def errorcodes_urls():
    yield 'errorcodes', {}


@freezer.register_generator
def index_urls():
    for version in VERSIONS:
        yield 'index', {'version': version}


@freezer.register_generator
def featuretype_list_urls():
    for version in VERSIONS:
        yield 'featuretype_list', {'version': version}


@freezer.register_generator
def featuretype_tree_urls():
    for version in VERSIONS:
        yield 'featuretype_tree', {'version': version}


@freezer.register_generator
def restriktioner_urls():
    for version in VERSIONS:
        yield 'restriktioner', {'version': version}


@freezer.register_generator
def general_constraints_urls():
    for version in VERSIONS:
        yield 'general_constraints', {'version': version}


@freezer.register_generator
def featuretype_summary_urls():
    for version in VERSIONS:
        for ft in get_featuretyper(version):
            yield 'featuretype_summary', {'version': version, 'navn': ft['navn']}


@freezer.register_generator
def docx_details_urls():
    for version in VERSIONS:
        for ft in get_featuretyper(version):
            yield 'docx_details', {'version': version, 'navn': ft['navn']}


@freezer.register_generator
def xsdelement_details_urls():
    for version in VERSIONS:
        for elmdict in get_xsdelement_details(version):
            yield 'xsdelement_details', {'version': version, 'slug': anchor_filter(elmdict['elm'].prefixed_name)}


@freezer.register_generator
def xsdtype_details_urls():
    for version in VERSIONS:
        for xsdtype, _chain in get_chains(version):
            yield 'xsdtype_details', {'version': version, 'slug': anchor_filter(xsdtype.prefixed_name)}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'freeze':
        freezer.freeze()
        # Stop GitHub Pages from running the output through Jekyll.
        (Path(app.config['FREEZER_DESTINATION']) / '.nojekyll').touch()
        print(f'Frozen to {app.config["FREEZER_DESTINATION"]}')
    else:
        app.run(debug=True)
