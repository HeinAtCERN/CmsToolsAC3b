import settings
import postprocessing
import generators as gen
import monitor
import os, re


class StackPlotterFS(postprocessing.PostProcTool):
    """A 'stack with data overlay' plotter. To be subclassed."""

    def __init__(self, name, histo_filter_dict):
        super(StackPlotterFS, self).__init__(name)
        self.histo_filter_dict = histo_filter_dict

    def run(self):
        """Load, stack, print and save histograms in a stream."""

        stream_stack = gen.fs_mc_stack_n_data_sum(
            {"analyzer":re.compile("CrtlFilt*")}
        )

        stream_stack = gen.pool_store_items(stream_stack)

        stream_stack = gen.debug_printer(stream_stack, False)

        stream_canvas = gen.canvas(
            stream_stack,
            #[rendering.Legend]
        )

        stream_canvas = gen.debug_printer(stream_canvas, False)

        stream_canvas = gen.save(
            stream_canvas,
            lambda wrp: self.plot_output_dir + wrp.name,
            settings.rootfile_postfixes
        )

        count = gen.consume_n_count(stream_canvas)
        self.message("INFO: "+self.name+" produced "+str(count)+" canvases.")


class SimpleWebCreator(postprocessing.PostProcTool):
    """
    Browses through settings.DIR_PLOTS and generates webpages recursively for
    all directories.
    """

    def __init__(self, name = None):
        super(self.__class__, self).__init__(name)
        self.working_dir = ""
        self.web_lines = []
        self.subfolders = []
        self.image_names = []
        self.image_postfix = None

    def _set_plot_output_dir(self):
        pass

    def configure(self):
        """A bit of initialization."""
        if not self.working_dir:
            self.working_dir = settings.DIR_PLOTS

        # get image format
        for pf in [".png", ".jpg", ".jpeg"]:
            if pf in settings.rootfile_postfixes:
                self.image_postfix = pf
                break
        if not self.image_postfix:
            self.message("WARNING: No image formats for web available!")
            self.message("WARNING: settings.rootfile_postfixes:"
                         + str(settings.rootfile_postfixes))
            return

        # collect folders and images
        for wd, dirs, files in os.walk(self.working_dir):
            self.subfolders += dirs
            for f in files:
                if f[-5:] == ".info":
                    self.image_names.append(f[:-5])
            break

        # first lines for the html page
        self.web_lines += ["<html>", "<body>", ""]

    def go4subdirs(self):
        """Walk of subfolders and start instances. Remove empty dirs."""
        for sf in self.subfolders[:]:
            path = os.path.join(self.working_dir, sf)
            inst = self.__class__()
            inst.working_dir = path
            inst.run()
            if not os.path.exists(os.path.join(path, "index.html")):
                self.subfolders.remove(sf)

    def make_headline(self):
        self.web_lines += (
            '<h1> Folder: ' + self.working_dir + '</h1>',
            '<hr width="60%">',
            ""
        )

    def make_subfolder_links(self):
        self.web_lines += ('<h2>Subfolders:</h2>',)
        for sf in self.subfolders:
            self.web_lines += (
                '<p><a href="'
                + os.path.join(sf, "index.html")
                + '">'
                + sf
                + '</a></p>',
            )
        self.web_lines += ('<hr width="60%">', "")

    def make_image_divs(self):
        self.web_lines += ('<h2>Images:</h2>',)
        for img in self.image_names:
            self.web_lines += (
                '<p>',
                '<h3>' + img + ":</h3>"
                '<img src="'
                + img + self.image_postfix
                + '" />',
                '</p>',
                '<hr width="95%">'
            )
        #TODO: Integrate image history into webpage

    def finalize_page(self):
        self.web_lines += ["", "</body>", "</html>", ""]

    def write_page(self):
        """Write to disk."""
        for i,l in enumerate(self.web_lines):
            self.web_lines[i] += "\n"
        with open(os.path.join(self.working_dir, "index.html"), "w") as f:
            f.writelines(self.web_lines)

    def run(self):
        """Run the single steps."""
        self.configure()
        if not self.image_postfix: return # WARNING message above.
        if not (self.image_names or self.subfolders): return # Nothing to do
        self.go4subdirs()
        self.make_headline()
        self.make_subfolder_links()
        self.make_image_divs()
        self.finalize_page()
        self.write_page()


