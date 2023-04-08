from hooks import webservice
webservice.start()

if __name__ == "__main__":
    import hooks.monitor
    hooks.monitor.StartUp()
