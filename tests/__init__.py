def create_contestant_data(amount=4):
    contestant_names = [
        "Contesto Uno",
        "Contesto Dos",
        "Contesto Tres",
        "Contesto Quatro",
        "Contesto Cinco",
        "Contesto Seis",
        "Contesto Siete",
        "Contesto Ocho",
        "Contesto Nueve",
        "Contesto Diez",
    ]
    contestant_colors = [
        "#1FC466",
        "#1155EE",
        "#BD1D1D",
        "#CA12AF",
        "#5A03C4",
        "#EBE807",
        "#FF8000",
        "#1B8524",
        "#00CCFF",
        "#9E9CD6",
    ]

    return contestant_names[:amount], contestant_colors[:amount]
