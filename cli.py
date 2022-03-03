def client():
    print("\n        NBC Client        \n")
    while(True):
        cli_input = input()
        if cli_input[0:2] == "t ":
            print("New transaction requested")
        elif cli_input == "view":
            print("View requested")
        elif cli_input == "balance":
            print("Balance requested")
        else:
            if cli_input != "help":
                print("Command not recognized")
            print("\nAvailable Commands:")
            print("t <recipient_address> <amount>: Create new transaction.")
            print("view:                           View transactions in last block.")
            print("balance:                        Show balance of wallet.")
            print("help:                           Show available commands.\n\n")
