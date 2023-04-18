#!/usr/bin/env python3

types = {
    "BASIC_CONSTRAINTS": {
        "ca": "ca_bool_int",
        "pathlen": "ASN1_INTEGER",
    },
}

getter_conv_tmpl = {
    "ca_bool_int": "ctx.{k} == 0xFF",
    "ASN1_INTEGER": "tonumber(C.ASN1_INTEGER_get(ctx.{k}))",
}

setter_conv_tmpl = {
    "ca_bool_int": '''
  toset.{k} = cfg_lower.{k} and 0xFF or 0''',
    "ASN1_INTEGER": '''
  local {k} = cfg_lower.{k} and tonumber(cfg_lower.{k})
  if {k} then
    C.ASN1_INTEGER_free(toset.{k})

    local asn1 = C.ASN1_STRING_type_new({k})
    if asn1 == nil then
      return false, format_error("x509:set_{type}: ASN1_STRING_type_new")
    end
    toset.{k} = asn1

    local code = C.ASN1_INTEGER_set(asn1, {k})
    if code ~= 1 then
      return false, format_error("x509:set_{type}: ASN1_INTEGER_set", code)
    end
  end'''
}

c2t_assign_locals = '''
  local {k} = {conv}'''

c2t_return_table = '''
      {k} = {k},'''

c2t_return_partial = '''
  elseif string.lower(name) == "{k}" then
    got = {k}'''

c2t = '''
  local ctx = ffi_cast("{type}*", got)
{assign_locals}

  C.{type}_free(ctx)

  if not name or type(name) ~= "string" then
    got = {{
{return_table}
    }}
{return_partial}
  end
'''

t2c = '''
  local cfg_lower = {{}}
  for k, v in pairs(toset) do
    cfg_lower[string.lower(k)] = v
  end

  toset = C.{type}_new()
  if toset == nil then
    return false, format_error("x509:set_{type}")
  end
  ffi_gc(toset, C.{type}_free)
{set_members}
'''
# getter
def c_struct_to_table(name):
    t = types[name]
    return c2t.format(
        type=name,
        assign_locals="".join([
            c2t_assign_locals.format(
                k=k,
                conv=getter_conv_tmpl[v].format(k=k)
            )
            for k, v in t.items()
        ]),
        return_table="".join([
            c2t_return_table.format(k=k)
            for k in t
        ]).lstrip("\n"),
        return_partial="".join([
            c2t_return_partial.format(k=k)
            for k in t
        ]).lstrip("\n"),
    ) 

# setter
def table_to_c_struct(name):
    t = types[name]
    return t2c.format(
        type=name,
        set_members="".join([
            setter_conv_tmpl[v].format(
                k=k,
                type=name,
            )
            for k, v in t.items()
        ]),
    )