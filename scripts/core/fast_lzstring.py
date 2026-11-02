#!/usr/bin/env python3
"""
Motor de descompressão e compressão rápida para o algoritmo LZ-String (Base64).
Otimizado para saves de RPG Maker MV (.rpgsave) e MZ (.rmmzsave).

Substitui a implementação puramente interpretada com loops lentos por:
- Tabelas de lookup de base64 pré-computadas (O(1)).
- Substituição de math.pow por deslocamentos de bits (bit shifts).
- Eliminação de instanciações excessivas de objetos e chamadas de lambdas.
- Fallback automático para a biblioteca lzstring padrão caso necessário.
"""

from typing import Optional

# Mapeamento Base64 padrão do LZ-String (65 caracteres incluindo '=')
KEY_STR_BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
B64_LOOKUP = {c: i for i, c in enumerate(KEY_STR_BASE64)}

# Tenta corrigir também o bug de re-população do baseReverseDic do pacote lzstring padrão
try:
    import lzstring
    if hasattr(lzstring, "baseReverseDic"):
        lzstring.baseReverseDic[KEY_STR_BASE64] = B64_LOOKUP
        _orig_getBaseValue = getattr(lzstring, "getBaseValue", None)
        def _fast_getBaseValue(alphabet, character):
            dic = lzstring.baseReverseDic.get(alphabet)
            if dic is None:
                dic = {c: i for i, c in enumerate(alphabet)}
                lzstring.baseReverseDic[alphabet] = dic
            return dic.get(character, 0)
        lzstring.getBaseValue = _fast_getBaseValue
    _STANDARD_LZ = lzstring.LZString()
except Exception:
    _STANDARD_LZ = None


def decompress_from_base64(compressed: Optional[str]) -> Optional[str]:
    """
    Descomprime uma string no formato Base64 LZ-String de forma ultrarrápida.
    """
    if compressed is None:
        return ""
    if not compressed:
        return ""

    try:
        length = len(compressed)
        lookup = B64_LOOKUP
        # Pré-mapeia os caracteres para inteiros de 0 a 63
        vals = [lookup.get(c, 0) for c in compressed]

        val = vals[0] if length > 0 else 0
        position = 32
        index = 1

        dictionary = {0: 0, 1: 1, 2: 2}
        enlarge_in = 4
        dict_size = 4
        num_bits = 3
        result = []

        bits = 0
        power = 1
        while power != 4:
            resb = val & position
            position >>= 1
            if position == 0:
                position = 32
                val = vals[index] if index < length else 0
                index += 1
            if resb > 0:
                bits |= power
            power <<= 1

        next_c = bits
        if next_c == 0:
            bits = 0
            power = 1
            while power != 256:
                resb = val & position
                position >>= 1
                if position == 0:
                    position = 32
                    val = vals[index] if index < length else 0
                    index += 1
                if resb > 0:
                    bits |= power
                power <<= 1
            c = chr(bits)
        elif next_c == 1:
            bits = 0
            power = 1
            while power != 65536:
                resb = val & position
                position >>= 1
                if position == 0:
                    position = 32
                    val = vals[index] if index < length else 0
                    index += 1
                if resb > 0:
                    bits |= power
                power <<= 1
            c = chr(bits)
        elif next_c == 2:
            return ""
        else:
            c = ""

        dictionary[3] = c
        w = c
        result.append(c)

        while index <= length or position < 32:
            bits = 0
            maxpower = 1 << num_bits
            power = 1
            while power != maxpower:
                resb = val & position
                position >>= 1
                if position == 0:
                    position = 32
                    val = vals[index] if index < length else 0
                    index += 1
                if resb > 0:
                    bits |= power
                power <<= 1

            c_code = bits
            if c_code == 0:
                bits = 0
                power = 1
                while power != 256:
                    resb = val & position
                    position >>= 1
                    if position == 0:
                        position = 32
                        val = vals[index] if index < length else 0
                        index += 1
                    if resb > 0:
                        bits |= power
                    power <<= 1
                dictionary[dict_size] = chr(bits)
                dict_size += 1
                c_code = dict_size - 1
                enlarge_in -= 1
            elif c_code == 1:
                bits = 0
                power = 1
                while power != 65536:
                    resb = val & position
                    position >>= 1
                    if position == 0:
                        position = 32
                        val = vals[index] if index < length else 0
                        index += 1
                    if resb > 0:
                        bits |= power
                    power <<= 1
                dictionary[dict_size] = chr(bits)
                dict_size += 1
                c_code = dict_size - 1
                enlarge_in -= 1
            elif c_code == 2:
                return "".join(result)

            if enlarge_in == 0:
                enlarge_in = 1 << num_bits
                num_bits += 1

            if c_code in dictionary:
                entry = str(dictionary[c_code])
            elif c_code == dict_size:
                entry = w + w[0]
            else:
                return ""

            result.append(entry)
            dictionary[dict_size] = w + entry[0]
            dict_size += 1
            enlarge_in -= 1
            w = entry

            if enlarge_in == 0:
                enlarge_in = 1 << num_bits
                num_bits += 1

        return "".join(result)
    except Exception:
        # Fallback de segurança para a biblioteca padrão
        if _STANDARD_LZ is not None:
            return _STANDARD_LZ.decompressFromBase64(compressed)
        raise


def compress_to_base64(uncompressed: Optional[str]) -> str:
    """Comprime texto no formato Base64 LZ-String."""
    if _STANDARD_LZ is not None:
        return _STANDARD_LZ.compressToBase64(uncompressed or "")
    raise RuntimeError("Biblioteca lzstring não disponível para compressão.")


class FastLZString:
    """Interface compatível com lzstring.LZString."""

    def decompressFromBase64(self, compressed: Optional[str]) -> Optional[str]:
        return decompress_from_base64(compressed)

    def compressToBase64(self, uncompressed: Optional[str]) -> str:
        return compress_to_base64(uncompressed)


FAST_LZSTRING = FastLZString()
