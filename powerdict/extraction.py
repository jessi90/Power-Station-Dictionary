# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02-attribute extraction.ipynb (unless otherwise specified).

__all__ = ['get_field_name_tags', 'field_hierarchies_to_root', 'assign_idx_fields', 'initialise_site_data_with_ids',
           'get_dict_head', 'datapackage_ref_to_ds_schema', 'init_datapackage_ref',
           'extract_external_foreignkey_datapackage_refs', 'add_resource_locs_to_external_datapackage_refs',
           'create_dir', 'download_attribute_data_to_temp_dir', 'load_datapackage', 'load_resource_attr_dfs',
           'load_dataset_ref', 'get_datapackage_ref', 'load_full_id_map', 'determine_matched_ids',
           'delete_null_attributes', 'delete_null_values', 'format_attr_value_type', 'format_all_attr_value_types',
           'extract_attrs_from_resource_dfs', 'flatten_list', 'drop_duplicates_attrs', 'json_nan_to_none',
           'construct_dictionary_knowledge_graph']

# Cell
import json
from json.decoder import JSONDecodeError
import numpy as np
import pandas as pd

import os
import typing
import datetime
from warnings import warn

import urllib
import urllib.parse
from urllib.request import urlopen, urlretrieve

from frictionless import Package

# Cell
def get_field_name_tags(
    schema: dict,
    ids_resource_name: str='ids'
):
    field_name_tags = {
        field['name']: field['hierarchy']
        for field
        in schema['fields']
    }

    return field_name_tags

def field_hierarchies_to_root(field_hierarchies: dict):
    root_fields = [k for k, v in field_hierarchies.items() if v=='root']

    assert len(root_fields) == 1, 'There can be only 1 field with the hierarchy: `root`'
    root_field = root_fields[0]

    return root_field

def assign_idx_fields(df, index, root_field_type, alt_indexes=None, int_types=['integer']):
    if not isinstance(index, list):
        index = [index]

    if alt_indexes is not None:
        index = index + alt_indexes

    if df.index.name in index:
        df = df.reset_index()

    df = df.dropna(subset=index, how='all').copy()

    if root_field_type in int_types:
        df.index = df.index.astype(int)

    if len(set(index) - set(df.columns)) == 0:
        if root_field_type in int_types:
            df[index[0]] = df[index[0]].astype(int)

        df = df.set_index(index)

        assert df.index.unique().size == df.shape[0], 'There were duplicated values in the primary key field'
    else:
        raise ValueError(f'The expected primary key field, {primary_key_field}, is not within the dataset')

    return df

# Cell
get_dict_head = lambda dict_, n=5: pd.Series(dict_).head(n).to_dict()

def initialise_site_data_with_ids(df_ids, field_hierarchies):
    valid_hierarchy_types = ['root', 'parent', 'child', 'equivalent', 'equivalent/parent', 'equivalent/child']

    site_data = {}
    id_cols = df_ids.columns

    for idx, *ids in df_ids.itertuples():
        site_data[idx] = {}
        site_data[idx]['id_hierarchies'] = {}
        site_data[idx]['id_hierarchies']['parent'] = {}
        site_data[idx]['id_hierarchies']['child'] = {}
        site_data[idx]['id_hierarchies']['equivalent'] = {}

        for id_type, id_value in pd.Series(dict(zip(id_cols, ids))).dropna().items():
            field_hierarchy = field_hierarchies[id_type]
            assert field_hierarchy in valid_hierarchy_types, f'The {field_hierarchy} field did not have a valid hierarchical attribute'

            if 'equivalent/' in field_hierarchy:
                hierarchy_if_not_array, hierarchy_if_array = field_hierarchy.split('/')

                if isinstance(id_value, list):
                    if len(id_value) > 1:
                        site_data[idx]['id_hierarchies'][hierarchy_if_array][id_type] = id_value
                    else:
                        site_data[idx]['id_hierarchies'][hierarchy_if_not_array][id_type] = id_value[0]
            else:
                site_data[idx]['id_hierarchies'][field_hierarchy][id_type] = id_value

    return site_data

# Cell
def datapackage_ref_to_ds_schema(datapackage_ref):
    dp_url = datapackage_ref['package']
    resource = datapackage_ref['resource']

    try:
        dp_schema = json.load(urlopen(dp_url))
    except JSONDecodeError:
        raise Exception(f'Failed to decode {resource}')

    ds_schema = [
        resource
        for resource
        in dp_schema['resources']
        if resource['name'] == datapackage_ref['resource']
    ][0]

    return ds_schema

def init_datapackage_ref(fk):
    datapackage_ref = {
        'package': fk['reference']['package'],
        'resource': fk['reference']['resource'],
        'attributes': fk['reference']['attributes'],
        'dictionary_pk_field': fk['fields'],
        'external_fk_field': fk['reference']['fields']
    }

    if 'alt_indexes' in fk['reference'].keys():
        datapackage_ref['alt_indexes'] = fk['reference']['alt_indexes']

    return datapackage_ref

def extract_external_foreignkey_datapackage_refs(resource, primary_key_field):
    fk_external_datapackage_refs = [
        init_datapackage_ref(fk)
        for fk
        in resource.schema['foreignKeys']
        if ('package' in fk['reference'].keys())
    ]

    for i, datapackage_ref in enumerate(fk_external_datapackage_refs):
        try:
            ds_schema = datapackage_ref_to_ds_schema(datapackage_ref)
            fk_external_datapackage_refs[i]['attribute_fields'] = {field['name']: field for field in ds_schema['schema']['fields']}
        except urllib.error.URLError as exception:
            warn(f'{datapackage_ref["resource"]} could not be processed.\n\n{exception}')

    return fk_external_datapackage_refs

# Cell
def add_resource_locs_to_external_datapackage_refs(fk_external_datapackage_refs: str) -> dict:
    for i, fk_external_datapackage_ref in enumerate(fk_external_datapackage_refs):
        external_datapackage_basepath = '/'.join(fk_external_datapackage_ref['package'].split('/')[:-1])

        try:
            external_datapackage_json = json.load(urlopen(fk_external_datapackage_ref['package']))

            fk_external_datapackage_refs[i]['resource_loc'] = [
                f"{external_datapackage_basepath}/{resource['path']}"
                for resource
                in external_datapackage_json['resources']
                if resource['name'] == fk_external_datapackage_ref['resource']
            ][0]

            fk_external_datapackage_refs[i]['name'] = external_datapackage_json['name']
        except urllib.error.URLError as exception:
            warn(f'{fk_external_datapackage_ref["resource"]} could not be processed.\n\n{exception}')

    return fk_external_datapackage_refs

# Cell
def create_dir(dir_loc: str='./temp', warn=False):
    if not os.path.isdir(dir_loc):
        os.mkdir(dir_loc)
    elif warn == True:
        warn(f'The directory `{dir_loc}` already exists')

    return None

def download_attribute_data_to_temp_dir(
    fk_external_datapackage_refs: dict,
    temp_dir_loc: str='./temp'
):
    create_dir(temp_dir_loc)

    for fk_external_datapackage_ref in fk_external_datapackage_refs:
        datapackage_name = fk_external_datapackage_ref['name']
        datapackage_files = [fk_external_datapackage_ref['resource_loc'], fk_external_datapackage_ref['package']]

        datapackage_temp_dir = f'{temp_dir_loc}/{datapackage_name}'
        create_dir(datapackage_temp_dir)

        for file_to_download in datapackage_files:
            filename = file_to_download.split('/')[-1]
            filepath = f'{datapackage_temp_dir}/{filename}'

            if os.path.exists(filepath):
                os.remove(filepath)

            file_to_download = file_to_download.replace(' ', '%20')
            urlretrieve(file_to_download, filepath)

    return

# Cell
def load_datapackage(datapackage_ref, temp_dir_loc='./temp', return_type='df', set_index=True):
    datapackage_resource = datapackage_ref['resource']
    external_datapackage = Package(datapackage_ref['package'])
    resource = external_datapackage.get_resource(datapackage_resource)

    if return_type == 'package':

        return external_datapackage
    elif return_type == 'resource':
        return resource

    elif return_type == 'df':
        df_resource = resource.to_pandas()

        if set_index == True:
            assert isinstance(datapackage_ref['external_fk_field'], str) or len(datapackage_ref['external_fk_field']==1), 'Only one primary key was expected to be matched on in the external datapackage'
            field_types = [field['type'] for field in resource.schema['fields'] if field['name']==datapackage_ref['external_fk_field']]
            field_names = [field['name'] for field in resource.schema['fields']]
            assert len(field_types) == 1, f'Expected only one field type, instead received: {", ".join(field_types)} for {datapackage_ref["external_fk_field"]}, {field_names}'
            field_type = field_types[0]

            if 'alt_indexes' in datapackage_ref.keys():
                alt_indexes = datapackage_ref['alt_indexes']
            else:
                alt_indexes = None

            df_resource = assign_idx_fields(df_resource, datapackage_ref['external_fk_field'], field_type, alt_indexes)

        return df_resource

    else:
        raise ValueError('`` must be one of ["df", "resource", "package"]')
        return resource

def load_resource_attr_dfs(fk_external_datapackage_refs, temp_dir_loc):
    resource_attr_dfs = []

    for datapackage_ref in fk_external_datapackage_refs:
        df_external_resource_attrs = load_datapackage(datapackage_ref, temp_dir_loc=temp_dir_loc)

        attrs_to_extract = datapackage_ref['attributes']
        df_external_resource_attrs = df_external_resource_attrs[attrs_to_extract]

        df_external_resource_attrs.name = datapackage_ref['package']
        resource_attr_dfs += [df_external_resource_attrs]

    return resource_attr_dfs

# Cell
get_datapackage_ref = lambda datapackage_refs, datapackage_url: [dp_ref for dp_ref in datapackage_refs if dp_ref['package']==datapackage_url][0]

def load_dataset_ref(datapackage_url, datapackage_refs, temp_dir_loc='./temp'):
    dp_ref = get_datapackage_ref(datapackage_refs, datapackage_url)
    package = load_datapackage(dp_ref, temp_dir_loc=temp_dir_loc, return_type='package')

    dataset_ref = {
        "datapackage_json_url": dp_ref['package'],
        "datapackage_name": dp_ref['name'],
        "related_resources": [
            {
                "resource_url": dp_ref['resource_loc'],
                "resource_name": dp_ref['resource'],
                "dictionary_pk_field": dp_ref['dictionary_pk_field'],
                "external_fk_field": dp_ref['external_fk_field'],
                "extracted_attributes": dp_ref['attributes']
            }
        ]
    }

    if 'description' in package.keys():
        dataset_ref["datapackage_description"]: package['description']
    if 'alt_indexes' in dp_ref.keys():
        dataset_ref['related_resources'][0]['alt_indexes'] = dp_ref['alt_indexes']

    return dataset_ref

# Cell
flatten_list = lambda list_: [item for sublist in list_ for item in sublist]
drop_duplicates_attrs = lambda attrs, subset=None: pd.DataFrame(attrs).pipe(lambda df: df.loc[df.astype(str).drop_duplicates(subset=subset).index]).to_dict(orient='records')

def load_full_id_map(single_site_data):
    full_id_map = {}

    for hierarchy_ids in single_site_data['id_hierarchies'].values():
        full_id_map.update(hierarchy_ids)

    return full_id_map

def determine_matched_ids(df_resource_attrs, dict_ids):
    if isinstance(df_resource_attrs.index, pd.core.indexes.multi.MultiIndex):
        primary_index = df_resource_attrs.index.get_level_values(0)
    else:
        primary_index = df_resource_attrs.index

    matched_dict_ids = list(set(primary_index).intersection(set(dict_ids)))
    matched_dict_ids = [dict_id for dict_id in dict_ids if dict_id in matched_dict_ids]

    return matched_dict_ids

def delete_null_attributes(site_data):
    for site_id, site_attributes in site_data.items():
        if 'attributes' in site_attributes.keys():
            for idx, attribute in enumerate(site_attributes['attributes']):
                if isinstance(attribute['value'], float):
                    if np.isnan(attribute['value']) or attribute['value']=='nan':
                        site_data[site_id]['attributes'].remove(attribute)

    return site_data

def delete_null_values(_dict, null_values=[None, np.nan, 'nan']):
    for key, value in list(_dict.items()):
        if isinstance(value, dict):
            delete_none(value)
        elif value in null_values:
            del _dict[key]
        elif isinstance(value, list):
            for v_i in value:
                if v_i in null_values:
                    del v_i

    return _dict

def format_attr_value_type(attr_value):
    if isinstance(attr_value, datetime.date):
        return attr_value.strftime('%Y-%m-%d')

    if isinstance(attr_value, datetime.datetime):
        return attr_value.strftime('%Y-%m-%d %H:%M')

    if isinstance(attr_value, pd.Timestamp):
        return attr_value.strftime('%Y-%m-%d %H:%M')

    return attr_value

def format_all_attr_value_types(site_data):
    for site, data in site_data.items():
        if 'attributes' in data.keys():
            for i, attr in enumerate(data['attributes']):
                site_data[site]['attributes'][i]['value'] = format_attr_value_type(attr['value'])

    return site_data

def extract_attrs_from_resource_dfs(site_data, datapackage_refs, temp_dir_loc, root_id='dictionary_id'):
    dp_schemas = {}
    resource_attr_dfs = load_resource_attr_dfs(datapackage_refs, temp_dir_loc)

    for site_id in site_data.keys():
        site_data[site_id]['datasets'] = {}
        full_id_map = load_full_id_map(site_data[site_id])
        full_id_map[root_id] = site_id

        for df_resource_attrs in resource_attr_dfs:
            dp_url = df_resource_attrs.name

            datapackage_ref = get_datapackage_ref(datapackage_refs, dp_url)
            dataset_ref = load_dataset_ref(df_resource_attrs.name, datapackage_refs, temp_dir_loc=temp_dir_loc)

            if datapackage_ref['dictionary_pk_field'] in full_id_map.keys():
                dict_ids = full_id_map[datapackage_ref['dictionary_pk_field']]

                if not isinstance(dict_ids, list):
                    dict_ids = [dict_ids]

                matched_dict_ids = determine_matched_ids(df_resource_attrs, dict_ids)

                if len(matched_dict_ids) > 0:
                    # datasets
                    if dp_url not in site_data[site_id]['datasets'].keys():
                        site_data[site_id]['datasets'][dp_url] = dataset_ref
                    else:
                        site_data[site_id]['datasets'][dp_url]['related_resources'] += dataset_ref['related_resources']

                    # attributes
                    if isinstance(df_resource_attrs.index, pd.core.indexes.multi.MultiIndex):
                        site_attrs_from_resource = []

                        for id_ in matched_dict_ids:
                            df_relevant_resource_attrs = df_resource_attrs.xs(id_, level=0)
                            df_relevant_resource_attrs = df_relevant_resource_attrs.dropna(how='all', axis=1)

                            if df_relevant_resource_attrs.shape[0] > 0:
                                site_attrs_from_resource += [df_relevant_resource_attrs.to_dict()]

                    else:
                        site_attrs_from_resource = df_resource_attrs.loc[matched_dict_ids].dropna(how='all', axis=1).to_dict(orient='records')

                    def get_attribute_name(datapackage_ref, attribute):
                        if 'title' in datapackage_ref['attribute_fields'][attribute]:
                            return datapackage_ref['attribute_fields'][attribute]['title']
                        else:
                            return attribute

                    reshaped_site_attrs = flatten_list([
                        [
                            {
                                'source': dp_url,
                                'id': dict_id,
                                'attribute': get_attribute_name(datapackage_ref, k),
                                'field_schema': datapackage_ref['attribute_fields'][k],
                                'value': v
                            }
                            for k, v
                            in dict_.items()
                            if (not pd.isnull(v)) and (v not in [None, np.nan, 'None', 'nan'])
                        ]
                        for dict_id, dict_
                        in zip(matched_dict_ids, site_attrs_from_resource)
                    ])

                    if len(site_attrs_from_resource) >= 1:
                        if 'attributes' not in site_data[site_id].keys():
                            site_data[site_id]['attributes'] = []

                        site_data[site_id]['attributes'] += reshaped_site_attrs

                        subset = list(set(site_data[site_id]['attributes'][0].keys())-{'field_schema'}) # this assumes all attribute entries have the same keys
                        site_data[site_id]['attributes'] = drop_duplicates_attrs(site_data[site_id]['attributes'], subset=subset)

    site_data = delete_null_attributes(site_data)
    site_data = format_all_attr_value_types(site_data)

    return site_data

# Cell
def json_nan_to_none(
    obj: typing.Any,
    *,
    json_constant_map: dict={'NaN': None},
    default: typing.Callable=None
) -> None:
    json_string = json.dumps(obj, default=default)
    cleaned_obj = json.loads(
        json_string,
        parse_constant=lambda constant: json_constant_map[constant],
    )

    return cleaned_obj

# Cell
def construct_dictionary_knowledge_graph(datapackage_fp, temp_dir_loc, resource_name='ids'):
    package = Package(datapackage_fp, profile='tabular-data-package')
    ids_resource = package.get_resource(resource_name)

    field_hierarchies = get_field_name_tags(ids_resource.schema)
    root_field = field_hierarchies_to_root(field_hierarchies)
    root_field_type = [field['type'] for field in ids_resource.schema['fields'] if field['name']==root_field][0]

    df_ids = assign_idx_fields(ids_resource.to_pandas(), root_field, root_field_type)
    site_data = initialise_site_data_with_ids(df_ids, field_hierarchies)

    fk_external_datapackage_refs = extract_external_foreignkey_datapackage_refs(ids_resource, primary_key_field=root_field)
    fk_external_datapackage_refs = add_resource_locs_to_external_datapackage_refs(fk_external_datapackage_refs)

    download_attribute_data_to_temp_dir(fk_external_datapackage_refs, temp_dir_loc=temp_dir_loc)
    site_data = extract_attrs_from_resource_dfs(site_data, fk_external_datapackage_refs, temp_dir_loc)
    site_data = json_nan_to_none(site_data)

    return site_data