from pymolpro import Project as BaseProject
class Project(BaseProject):
    def __init__(self, *args, **kwargs):
        self.run_directory = 0
        super().__init__(*args, **kwargs)

    def filename(self, suffix="", name="", run=0):
        if type(self.run_directory) != int:
            raise Exception('run_directory must be an integer ' + str(self.run_directory))
        # print('filename', suffix, 'name=',name, 'run=', run, 'self.run_directory=',self.run_directory)
        filename = super().filename(suffix, name, self.run_directory if run == 0 else run)
        # print('evaluated filename',filename)
        return filename

    @property
    def run_directory_names(self) -> list[str]:
        result = []
        dirs = self.property_get('run_directories')
        if dirs and 'run_directories' in dirs:
            result = [''] + dirs['run_directories'].strip().split(' ')
        return result

