"""
Apply hadd for a folder of histograms.
"""

import varial.multiproc
import varial.wrappers
import varial.analysis
import varial.diskio
import varial.pklio
import varial.tools

import glob
import os
join = os.path.join


def _handle_block(args):
    instance, name, files = args
    instance = varial.analysis.lookup_tool(instance)
    varial.multiproc.exec_in_worker(lambda: instance.handle_block(name, files))


class Hadd(varial.tools.Tool):
    """
    Apply hadd for a folder of histograms.

    All *.root files in the ``src_path`` directory that do not apply to one of
    the basenames are soft-linked into the new output directory.

    :param src_path:            str, *relative* path to input dir
    :param basenames:           list of str, basenames for files to be merged
                                (e.g. 'QCD' for 'QCD_XtoY', 'QCD_YtoZ'...)
    :param add_aliases_to_analysis:
                                bool, if true, analysis.fs_aliases are appended
                                with all output of this tool.
    :param name:                str, tool name
    """
    io = varial.pklio

    def __init__(self,
                 src_glob_path,
                 basenames,
                 add_aliases_to_analysis=True,
                 merge_trees=False,
                 samplename_func=lambda w: os.path.basename(w.file_path),
                 name=None):
        super(Hadd, self).__init__(name)
        self.src_glob_path = src_glob_path
        self.src_path = os.path.dirname(src_glob_path)
        self.basenames = basenames
        self.add_aliases_to_analysis = add_aliases_to_analysis
        self.merge_trees = merge_trees
        self.samplename_func = samplename_func
        assert(type(basenames) in (list, tuple))

    def produce_aliases(self):
        wrps = list(varial.diskio.generate_aliases(
                                            os.path.join(self.cwd, '*.root')))
        for w in wrps:
            w.sample = self.samplename_func(w)
        self.result = varial.wrappers.WrapperWrapper(wrps)
        os.system('touch %s/aliases.in.result' % self.cwd)

    def reuse(self):
        super(Hadd, self).reuse()
        if self.add_aliases_to_analysis:
            varial.analysis.fs_aliases += self.result.wrps

    def handle_block(self, basename, files):
        if not files:
            self.message('WARNING No files for basename: %s' % basename)
            return

        cmd = 'nice hadd -f -v 1 '
        if not self.merge_trees:
            cmd += '-T '
        cmd += join(self.cwd, basename) + '.root '
        cmd += ' '.join(files)
        os.system(cmd)

    def run(self):
        # sort input files
        input_files = glob.glob(join(self.cwd, self.src_glob_path))
        basename_map = dict((b, []) for b in self.basenames)
        other_inputs = []
        for inp_file in input_files:
            inp_file = os.path.basename(inp_file)
            file_path = join(self.cwd, self.src_path, inp_file)
            if any(inp_file.startswith(b) for b in self.basenames):
                for b in self.basenames:
                    if inp_file.startswith(b):
                        basename_map[b].append(file_path)
            else:
                other_inputs.append(file_path)

        # apply hadd in parallel
        pool = varial.multiproc.NoDeamonWorkersPool(
            min(varial.settings.max_num_processes, len(basename_map)))
        iterable = ((varial.analysis.get_current_tool_path(), bn, fs)
                    for bn, fs in basename_map.iteritems())

        for _ in pool.imap_unordered(_handle_block, iterable):
            pass

        pool.close()
        pool.join()

        # link others
        for f in other_inputs:
            os.system('ln -sf %s %s' % (os.path.relpath(f, self.cwd), self.cwd))

        # aliases
        self.produce_aliases()
        if self.add_aliases_to_analysis:
            varial.analysis.fs_aliases += self.result.wrps