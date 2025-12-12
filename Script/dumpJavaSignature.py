import sys
import re
import ctypes

# Mapping: Java Type -> (JNI Descriptor, Ctypes Type)
type_map = {
    "void":    ("V", None),
    "boolean": ("Z", ctypes.c_ubyte),  # jboolean is unsigned 8-bit
    "byte":    ("B", ctypes.c_byte),
    "char":    ("C", ctypes.c_uint16), # jchar is unsigned 16-bit
    "short":   ("S", ctypes.c_short),
    "int":     ("I", ctypes.c_int),
    "long":    ("J", ctypes.c_int64),  # Java long is always 64-bit
    "float":   ("F", ctypes.c_float),
    "double":  ("D", ctypes.c_double),
    "String":  ("Ljava/lang/String;", ctypes.c_void_p),
    "Object":  ("Ljava/lang/Object;", ctypes.c_void_p),
}

def get_jni_signature(return_type, params):
    """Generates the JNI encoding (e.g., '(II)V')."""
    def get_type_sig(t_type):
        if t_type.endswith("[]"):
            return "[" + get_type_sig(t_type[:-2])
        if t_type in type_map:
            return type_map[t_type][0]
        # Fallback for custom classes: replace . with / and wrap in L...;
        formatted_type = t_type.replace('.', '/')
        return f"L{formatted_type};"

    param_sigs = [get_type_sig(p_type) for p_type, _ in params]
    return_sig = get_type_sig(return_type)
    return f"({''.join(param_sigs)}){return_sig}"

def get_ctypes_signature(return_type, params):
    """Generates the ctypes CFUNCTYPE."""
    def get_ctype(t_type):
        if t_type.endswith("[]"):
            return ctypes.c_void_p  # Arrays are objects (opaque pointers)
        if t_type in type_map:
            return type_map[t_type][1]
        return ctypes.c_void_p      # Objects are void pointers

    param_types = [get_ctype(p_type) for p_type, _ in params]

    # Handle return type
    ret_type = None if return_type == "void" else get_ctype(return_type)

    # Note: The first two arguments in JNI are always (JNIEnv*, jobject/jclass)
    # We set them as c_void_p here.
    return ctypes.CFUNCTYPE(ret_type, ctypes.c_void_p, ctypes.c_void_p, *param_types)

def parse_method_declaration(declaration):
    """
    Parses a Java method string regardless of modifier order.
    Example: "private native static int foo(String s)"
    """
    # 1. Separate Method Definition (left) from Parameters (right)
    if '(' not in declaration or ')' not in declaration:
        raise ValueError("Declaration must contain parenthesis '()'")

    def_part, params_part = declaration.split('(', 1)
    params_part = params_part.rsplit(')', 1)[0] # remove trailing ')'

    # 2. Tokenize the definition part (handling generics vaguely)
    # We replace generic brackets with underscores temporarily to avoid splitting errors
    # if users input "List<String>".
    # (A real parser is better, but this suffices for single-line inputs)
    clean_def = re.sub(r'<[^>]+>', '', def_part)
    tokens = clean_def.split()

    if len(tokens) < 2:
        raise ValueError("Declaration too short. Needs at least ReturnType and MethodName.")

    # In Java, the last token before '(' is the Method Name
    method_name = tokens[-1]
    # The second to last is the Return Type
    return_type = tokens[-2]
    # Everything else are modifiers
    modifiers = tokens[:-2]

    # Check for 'native'
    if "native" not in modifiers:
        print("Warning: 'native' keyword missing. Proceeding anyway...")

    # Check for 'static'
    is_static = "static" in modifiers

    # 3. Parse Parameters
    params = []
    if params_part.strip():
        # Split by comma
        raw_params = params_part.split(',')
        for raw_p in raw_params:
            raw_p = raw_p.strip()
            # Regex to grab type and name: "String arg0" or "int[] numbers"
            # We ignore keywords like final or annotations for the signature
            parts = raw_p.split()
            if not parts: continue

            # Usually the type is the second-to-last word if modifiers exist,
            # or first word if simple.
            # Heuristic: The Type is the word immediately preceding the Variable Name.
            if len(parts) >= 2:
                p_type = parts[-2]
            else:
                p_type = parts[0] # Just a type, no variable name provided

            params.append((p_type, False))

    return method_name, return_type, params, is_static

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python jni_sig.py \"<Java Declaration>\"")
        print("\nExample Test:")
        test_decl = "private native static int[] myMethod(int count, String msg)"
        print(f"Input: {test_decl}")

        try:
            name, ret, params, is_static = parse_method_declaration(test_decl)
            jni = get_jni_signature(ret, params)
            c_sig = get_ctypes_signature(ret, params)

            print(f"Method: {name}")
            print(f"Is Static: {is_static}")
            print(f"JNI Sig: {jni}")
            print(f"ctypes: {c_sig}")
        except Exception as e:
            print(e)
        sys.exit(0)

    decl = sys.argv[1]
    try:
        name, ret, params, is_static = parse_method_declaration(decl)
        jni = get_jni_signature(ret, params)
        c_sig = get_ctypes_signature(ret, params)

        print(f"Method Name: {name}")
        print(f"Is Static: {is_static}")
        print(f"JNI Signature: {jni}")
        print(f"ctypes Signature: {c_sig}")
    except ValueError as e:
        print(f"Error: {e}")