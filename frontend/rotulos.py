"""Nomes legíveis dos níveis (camada de apresentação). Os efeitos já chegam rotulados da API."""

NIVEIS = {
    # tema em 7 grupos (BDR-009)
    "tarefa_conhecimento": "Tarefa (conhecimento, estudo, trabalho)",
    "saudacao_teste": "Saudação ou teste",
    "programacao_tecnologia": "Programação e tecnologia",
    "criativo_entretenimento": "Criativo e entretenimento",
    "traducao_reescrita": "Tradução e reescrita",
    "conselho_pessoal": "Conselho pessoal",
    "outro": "Outro",
    # 11 temas (descritivo)
    "conhecimento_geral": "Conhecimento geral",
    "estudo_escola": "Estudo e escola",
    "trabalho_profissional": "Trabalho",
    "criativo_ficcao": "Criativo e ficção",
    "roleplay_personagem": "Roleplay",
    "conteudo_adulto": "Conteúdo adulto",
    # modelo, dispositivo, idioma, horário, resposta, recusa
    "gpt-3.5": "GPT-3.5", "gpt-4": "GPT-4",
    "desktop": "Desktop", "mobile": "Celular",
    "portugues": "Português", "ingles": "Inglês",
    "madrugada": "Madrugada (0–5h)", "manha": "Manhã (6–11h)", "tarde": "Tarde (12–17h)", "noite": "Noite (18–23h)",
    "Q1": "1º quartil (curta)", "Q2": "2º quartil", "Q3": "3º quartil", "Q4": "4º quartil (longa)",
    "sim": "Com recusa total", "nao": "Sem recusa total",
    "sem_valor": "Sem informação", "outros": "Outros estados",
}

DIMENSOES = {
    "tema_grupo": "Tema da 1ª conversa",
    "familia_modelo": "Modelo",
    "dispositivo": "Dispositivo",
    "idioma_3": "Idioma",
    "faixa_horaria": "Horário da estreia",
    "resposta_quartil": "Tamanho da 1ª resposta",
    "recusa_total": "Recusa total na 1ª conversa",
    "estado_grupo": "Estado",
    "tema": "Tema (11 categorias)",
}


def nivel(v: str) -> str:
    return NIVEIS.get(v, v)
