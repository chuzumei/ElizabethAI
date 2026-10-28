class SkillRegistry:
    def __init__(self):
        self._skills = {}

    def register(self, name, description, tools=None):
        self._skills[name] = {
            "name": name,
            "description": description,
            "tools": tools or [],
        }

    def get(self, name):
        return self._skills.get(name)

    def all(self):
        return list(self._skills.values())

    def names(self):
        return list(self._skills.keys())

    def find_by_tool(self, tool_name):
        for skill in self._skills.values():
            if tool_name in skill["tools"]:
                return skill
        return None


registry = SkillRegistry()
