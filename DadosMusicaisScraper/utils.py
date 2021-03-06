# -*- coding: utf-8 -*-
from pymongo import MongoClient

__author__ = 'marcelo'

import logging
import urllib
import urllib2
import json
import re
from DadosMusicaisScraper.settings import *

from music21 import chord
from music21 import interval
from music21 import harmony

LOG_FILENAME = 'utils.log'
logging.basicConfig(filename=LOG_FILENAME, filemode='w',
                    level=logging.ERROR)

notas_escala_sus = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']
notas_escala_bemol = ['A', 'B-', 'B', 'C', 'D-', 'D', 'E-', 'E', 'F', 'G-', 'G', 'A-']
idx_inicio_capo = [7, 12, 17, 22, 26, 31]
acordes_cache = {}
desenhos_acordes_cache = {}
idx_notas_acordes_cache = {}
notas_acordes_cache = {}


def eh_vazio(valor):
    retorno = False
    if valor is None or valor == '':
        retorno = True
    return retorno


def obter_valor_default(valor, valor_default):
    retorno = valor
    if eh_vazio(valor):
        retorno = valor_default
    return retorno


def obter_acorde_music21(acorde_str, capo=0, buscar_externamente=True):
    acorde = acordes_cache.get(acorde_str)
    if acorde == None and buscar_externamente:
        acorde, desenho_acorde_str, lista_idx_notas, lista_notas, flag_sucesso, msg = obter_acorde21_desenho_listanotas_idxnotas(
            acorde_str)

    interv_capo = interval.Interval(capo)
    acorde_com_capo = acorde.transpose(interv_capo)
    root = acorde.root()
    root = root.transpose(interv_capo)
    bass = acorde.bass()
    bass = bass.transpose(interv_capo)

    acorde_com_capo.root(root)
    acorde_com_capo.bass(bass)
    # As referencias devem ser diferentes. Senao estamos mudando o objeto em cache
    assert acorde != acorde_com_capo
    return acorde_com_capo


def obter_acorde21_desenho_listanotas_idxnotas(acorde_str, desenho_acorde_str=None):
    if acorde_str in desenhos_acordes_cache:
        acorde = acordes_cache[acorde_str]
        desenho_acorde_str = desenhos_acordes_cache[acorde_str]
        idx_lista_notas_acorde = idx_notas_acordes_cache[acorde_str]
        lista_notas = notas_acordes_cache[acorde_str]
        return acorde, desenho_acorde_str, idx_lista_notas_acorde, lista_notas, True, 'Sucesso - Cache'
    else:
        try:
            if desenho_acorde_str == None or len(desenho_acorde_str) == 0:
                try:
                    desenho_acorde_str = obter_desenho_echord(acorde_str)
                except BaseException as exc:
                    desenho_acorde_str = obter_desenho_cifraclub(acorde_str)

            # Verificamos se trata-se de uma nota bemol. Se sim, usamos a escala de bemol.
            match_bemol = re.match("^([A-G]b)", acorde_str)
            if match_bemol != None:
                lista_notas_escala = notas_escala_bemol
            else:
                lista_notas_escala = notas_escala_sus

            lista_idx_notas, lista_notas = obter_lista_idx_notas(desenho_acorde_str, lista_notas_escala)

            acorde = obter_acorde21(acorde_str, lista_notas)

            # Atualizo o cache
            acordes_cache[acorde_str] = acorde
            desenhos_acordes_cache[acorde_str] = acorde_str
            idx_notas_acordes_cache[acorde_str] = lista_idx_notas
            notas_acordes_cache[acorde_str] = lista_notas

            return acorde, desenho_acorde_str, lista_idx_notas, lista_notas, True, 'Sucesso'

        except BaseException as exc:
            # TODO VERIFICAR O TIPO DE ERRO
            return None, '', [], [], False, "Erro: %s" % exc


def obter_lista_idx_notas(desenho_acorde, escala=notas_escala_sus):
    desenho_acorde = desenho_acorde.split()
    lista_idx_notas = []
    lista_notas = []
    for i in range(0, 6):
        nota_str = desenho_acorde[i]
        if nota_str != "X":
            nota = int(nota_str)
            inicio_capo = idx_inicio_capo[i]
            idx_nota = (inicio_capo + nota) % 12
            oitava = int((inicio_capo + nota) / 12)
            nota_traduzida = escala[idx_nota] + str(oitava + 1)
            lista_idx_notas.append(idx_nota)
            lista_notas.append(nota_traduzida)

    return lista_idx_notas, lista_notas


def obter_acorde21(acorde_str, lista_notas):
    from music21 import pitch

    piches = [pitch.Pitch(nota) for nota in lista_notas]
    acorde = chord.Chord(piches)

    # TODO Talvez um acorde tenha tonica C e uma nota C#. Pode dar problema
    possiveis_tonicas = [nota for nota in lista_notas if nota[0] == acorde_str[0]]

    tonica = possiveis_tonicas[0]

    if len(possiveis_tonicas) > 1:
        match_nota_acidental = re.match('^[A-G](?:(?!\/\().)', acorde_str)
        if match_nota_acidental:
            possivel_tonica = match_nota_acidental.group()
            regex_tonica = re.compile(possivel_tonica)
            tonicas_encontradas = [nota for nota in lista_notas if regex_tonica.match(nota)]
            if len(tonicas_encontradas) > 0:
                tonica = tonicas_encontradas[0]

    acorde.bass()
    acorde.root(tonica)
    # o baixo é sempre a primeira nota da lista.
    acorde.bass(lista_notas[0])
    return acorde


def obter_desenho_cifraclub(acorde):
    acorde = substituir_caracteres_acorde(acorde)

    form_data = {'acorde': acorde, "capo": 0, 'afinacao': 'E-A-D-G-B-E', 'casas': 'X X X X X X', 'bcp': False}
    params = urllib.urlencode(form_data)
    response = urllib2.urlopen('http://www.cifraclub.com.br/ajax/dicionario.php', params)
    json_data = response.read()
    data = json.loads(json_data)
    # sinonimo = data['sinonimo']
    desenho_acorde_str = data['violao'][0]
    return desenho_acorde_str


def obter_desenho_echord(acorde):
    acorde = substituir_caracteres_acorde(acorde)

    form_data = {'type': '', "method": 2, 'chord': acorde}
    params = urllib.urlencode(form_data)

    response = urllib2.urlopen("http://www.e-chords.com/site/chords2.asp?" + params)
    html_data = response.read()

    import re

    desenho_acorde_str = re.search("variations':'(([0-9]|,|X)+)", html_data).group(1)

    return desenho_acorde_str.replace(",", " ")


def substituir_caracteres_acorde(acorde):
    regex_dim = u'(°|º|7\-)+'
    import re

    return re.sub(regex_dim, 'dim', acorde)


def obter_unicos_tonicas_baixos_modos(lista_acordes_str, capo=0):
    unicos = []
    tonicas = []
    baixos = []
    modos = []

    # Removo os duplicados.
    set_acordes_str = set(lista_acordes_str)

    for acorde_str in set_acordes_str:
        try:
            logging.info(u"Obtendo dados do acorde <%s>..." % acorde_str)
            acorde_21 = obter_acorde_music21(acorde_str, capo)
            nome_acorde = acorde_21.fullName
            tonica = acorde_21.root().name
            baixo = acorde_21.bass().name
            modo = acorde_21.commonName

            unicos.append(nome_acorde)
            tonicas.append(tonica)
            baixos.append(baixo)
            modos.append(modo)
        except BaseException as exc:
            logging.error(u"Erro ao traduzir o acorde: <%s>. Detalhes: %s" % (acorde_str, exc))
            raise exc

    return unicos, tonicas, baixos, modos


def carregar_dicionario_acordes():
    if len(desenhos_acordes_cache) == 0:
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        colecao = db[MONGODB_COLLECTION_DA]
        registros = colecao.find({'foi_sucesso': True})
        for registro in registros:
            try:
                ## TODO ACORDES QUE NAO COMECAO COM A-G DAO ERRO
                chave = registro["_id"]
                lista_notas = registro['lista_notas']
                desenho_acorde = registro["desenho_acorde"]
                idx_notas = registro['lista_idx_notas']

                acorde = obter_acorde21(chave, lista_notas)
                acordes_cache[chave] = acorde
                desenhos_acordes_cache[chave] = desenho_acorde
                idx_notas_acordes_cache[chave] = idx_notas
                notas_acordes_cache[chave] = lista_notas
            except BaseException as exc:
                logging.error(u"Erro ao traduzir o acorde na biblioteca music21: <%s>. Detalhes: %s" % (chave, exc))


if __name__ == '__main__':
    # import re
    #
    # acorde_str = "D7/B"
    # m = re.match("^.+\/([A-G])", acorde_str)
    # print(m)



    seq_acordes = [
        u"D°",
        "Abm",
        "D5",
        "A7(11+)",
        "Am(11+)",
        "D7/9",
        "Am6",
        "Em6",
        "Am7",
        "Am6",
        "Am7",
        "D7/9b"]

    acorde = 'Dbm7'
    # acorde21 = obter_acorde21_desenho_listanotas_idxnotas(acorde);

    # print(acorde21)
    acorde, desenho_acorde_str, lista_idx_notas, lista_notas, flag_sucesso, msg = obter_acorde21_desenho_listanotas_idxnotas(
        'E7(#9)')

    acorde_str, modo = harmony.chordSymbolFigureFromChord(acorde, True)

    acorde.quality

    acorde.pitchedCommonName
