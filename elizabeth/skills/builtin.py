from .registry import registry


def register_builtin_skills():
    registry.register(
        "system",
        "Controle do sistema operacional, volume, brilho, energia, bloqueio, informações do computador e notificações.",
        [
            "get_system_info",
            "set_volume",
            "get_volume",
            "set_brightness",
            "lock_screen",
            "power_command",
            "show_notification",
        ],
    )

    registry.register(
        "desktop",
        "Controle da área de trabalho, aplicativos, processos, janelas, teclado, mouse, tela, screenshots e reprodução de mídia.",
        [
            "open_app",
            "kill_process",
            "read_screen",
            "find_on_screen",
            "click_at",
            "scroll_screen",
            "move_mouse",
            "focus_window",
            "get_open_windows",
            "type_text",
            "press_key",
            "media_control",
            "screenshot",
        ],
    )

    registry.register(
        "clipboard",
        "Leitura e alteração do texto da área de transferência.",
        [
            "get_clipboard",
            "set_clipboard",
        ],
    )

    registry.register(
        "web",
        "Pesquisa na internet, consulta de páginas, abertura de URLs e informações meteorológicas.",
        [
            "web_search",
            "fetch_page",
            "open_url",
            "get_weather",
        ],
    )

    registry.register(
        "files",
        "Leitura, escrita e listagem de arquivos.",
        [
            "read_file",
            "write_file",
            "list_files",
        ],
    )

    registry.register(
        "development",
        "Execução de código Python e delegação de tarefas para modelos locais.",
        [
            "run_python",
            "delegate_task",
        ],
    )

    registry.register(
        "memory",
        "Memória e contexto persistente da Elizabeth.",
        [],
    )

    registry.register(
        "automation",
        "Timers, notificações e automações programadas.",
        [
            "set_timer",
            "show_notification",
        ],
    )


register_builtin_skills()
