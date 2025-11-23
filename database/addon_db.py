class AddonDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def set_AutoUpdates(self, PluginId, Value):
        self.cursor.execute("SELECT id FROM update_rules WHERE addonID = ?", (PluginId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("UPDATE update_rules SET updateRule = ? WHERE id = ?", (Value, Data[0]))
        else:
            self.cursor.execute("INSERT INTO update_rules (addonID, updateRule) VALUES (?, ?)", (PluginId, Value))
