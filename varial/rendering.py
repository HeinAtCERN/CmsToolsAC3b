"""
From histogram data to graphical plots.

The members of this package make plots from histograms or other wrapped
ROOT-objects. The 'Renderers' extend the functionality of wrappers for drawing.
The ROOT-canvas is build with the ``CanvasBuilder`` class.

Decorators can be used for customization of a ``CanvasBuilder`` instance.
They provide ways to add content to canvases, like a legend, boxes, lines,
text, etc.. See :ref:`util-module` for details on the decorator
implementation. Apply as below (e.g. with a 'Legend' or a 'TextBox'
Decorator)::

    cb = CanvasBuilder(wrappers)
    cb = Legend(cb, x1=0.2, x2=0.5)             # wrap cb with Legend
    cb = Textbox(cb, text="Some boxed Text")    # wrap Legend with Textbox
    canvas_wrp = cb.build_canvas()
"""


################################################################# renderers ###
import collections
import wrappers
import ROOT
from math import sqrt
import itertools
import ctypes


class Renderer(object):
    """
    Baseclass for rendered wrappers.
    """
    def __init__(self, wrp):
        self.val_x_min = 0.
        self.val_x_max = 0.
        self.val_y_min = 0.
        self.val_y_max = 0.
        self.__dict__.update(wrp.__dict__)

    def x_min(self):
        return self.val_x_min

    def x_max(self):
        return self.val_x_max

    def y_min(self):
        return self.val_y_min

    def y_max(self):
        return self.val_y_max

    def y_min_gr_zero(self):
        return self.y_min()

    def draw(self, option=''):
        pass


class HistoRenderer(Renderer, wrappers.HistoWrapper):
    """
    Extend HistoWrapper for drawing.
    """
    def __init__(self, wrp):
        super(HistoRenderer, self).__init__(wrp)
        if hasattr(wrp, 'draw_option'):
            self.draw_option = wrp.draw_option
        elif 'TH2' in wrp.type:
            self.draw_option = 'colz'
        elif self.is_data:
            self.draw_option = 'E0'
            # self.histo.SetBinErrorOption(ROOT.TH1.kPoisson)
            # self.histo.Sumw2(False)
        else:
            self.draw_option = 'hist'

    def x_min(self):
        return self.val_x_min or self.histo.GetXaxis().GetXmin()

    def x_max(self):
        return self.val_x_max or self.histo.GetXaxis().GetXmax()

    def y_min(self):
        # > 0 cuts away half numbers
        return self.val_y_min or self.histo.GetMinimum() + 1e-23

    def y_max(self):
        return self.val_y_max or self.histo.GetMaximum()

    def y_min_gr_zero(self, histo=None):
        if not histo:
            histo = self.histo
        nbins = histo.GetNbinsX()
        min_val = histo.GetMinimum()  # min on y axis
        if min_val < 1e-23 < histo.GetMaximum():  # should be greater than zero
            try:
                min_val = min(
                    histo.GetBinContent(i)
                    for i in xrange(nbins + 1)
                    if histo.GetBinContent(i) > 1e-23
                )
            except ValueError:
                min_val = 1e-23
        return min_val

    def draw(self, option=''):
        obj = getattr(self, 'graph_draw', self.histo)
        obj.Draw(self.draw_option + option)


class StackRenderer(HistoRenderer, wrappers.StackWrapper):
    """
    Extend StackWrapper for drawing.
    """
    def __init__(self, wrp):
        super(StackRenderer, self).__init__(wrp)

        if self.histo_sys_err:                          # calculate total error
            nom, sys, tot = self.histo, self.histo_sys_err, self.histo.Clone()
            for i in xrange(tot.GetNbinsX()+2):
                nom_val = nom.GetBinContent(i)
                nom_err = nom.GetBinError(i) or 1e-10   # prevent 0-div-error
                sys_val = sys.GetBinContent(i)
                sys_err = sys.GetBinError(i) or 1e-10   # prevent 0-div-error
                nom_wei = nom_err**2 / (nom_err**2 + sys_err**2)
                sys_wei = sys_err**2 / (nom_err**2 + sys_err**2)

                # weighted mean of values and quadratic sum of errors
                tot.SetBinContent(i, nom_wei*nom_val + sys_wei*sys_val)
                tot.SetBinError(i, (nom_err**2 + sys_err**2)**.5)

            self.histo_tot_err = tot
            # settings.sys_error_style(self.histo_sys_err)
            # settings.tot_error_style(self.histo_tot_err)

        settings.stat_error_style(self.histo)
        self.draw_option_sum = getattr(wrp, 'draw_option_sum', 'sameE2')

    def y_min_gr_zero(self, histo=None):
        return super(StackRenderer, self).y_min_gr_zero(
            self.stack.GetHists()[0]
        )

    def y_max(self):
        if self.histo_sys_err:
            return self.val_y_max or self.histo_tot_err.GetMaximum()
        else:
            return super(StackRenderer, self).y_max()

    def draw(self, option=''):
        for h in self.stack.GetHists():
            h.SetLineColor(ROOT.kGray)
        self.stack.Draw(self.draw_option + option)
        self.stack.GetXaxis().SetTitle(self.histo.GetXaxis().GetTitle())
        self.stack.GetYaxis().SetTitle(self.histo.GetYaxis().GetTitle())
        if self.histo_sys_err:
            settings.tot_error_style_main(self.histo_tot_err)
            self.histo_tot_err.Draw(self.draw_option_sum)
            # self.histo_sys_err.Draw(self.draw_option_sum)
        else:
            self.histo.Draw(self.draw_option_sum)


class GraphRenderer(Renderer, wrappers.GraphWrapper):
    """
    Extend GraphWrapper for drawing.
    """
    def __init__(self, wrp):
        super(GraphRenderer, self).__init__(wrp)
        if hasattr(wrp, 'draw_option'):
            self.draw_option = wrp.draw_option
        else:
            self.draw_option = 'P'

    def x_min(self):
        return self.val_x_min or self.graph.GetXaxis().GetXmin()

    def x_max(self):
        return self.val_x_max or self.graph.GetXaxis().GetXmax()

    def y_min(self):
        # > 0 cuts away half numbers
        return self.val_y_min or self.graph.GetYaxis().GetXmin() + 1e-23

    def y_max(self):
        return self.val_y_max or self.graph.GetYaxis().GetXmax()

    def draw(self, option=''):
        if 'same' in option:
            option.replace('same', '')
        else:
            option += 'A'
        self.graph.Draw(self.draw_option + option)


############################################################ canvas-builder ###
import settings
import history
from ROOT import TCanvas, TObject


def _renderize(wrp):
    if isinstance(wrp, Renderer):
        return wrp
    if isinstance(wrp, wrappers.GraphWrapper):
        return GraphRenderer(wrp)
    if isinstance(wrp, wrappers.StackWrapper):
        return StackRenderer(wrp)
    if isinstance(wrp, wrappers.HistoWrapper):
        return HistoRenderer(wrp)


def _renderize_iter(wrps):
    rnds = []
    for wrp in wrps:
        rnds.append(_renderize(wrp))
    return rnds


class CanvasBuilder(object):
    """
    Create a TCanvas and plot wrapped ROOT-objects.

    Use this class like so::

        cb = CanvasBuilder(list_of_wrappers, **kws)
        canvas_wrp = cb.build_canvas()

    * ``list_of_wrappers`` is can also be a list of renderers. If not, the
      renderers are created automatically.

    * ``**kws`` can be empty. Accepted keywords are ``name=`` and ``title=`` and
      any keyword that is accepted by ``histotools.wrappers.CanvasWrapper``.

    When designing decorators, these instance data members can be of interest:

    ================= =========================================================
    ``x_bounds``      Bounds of canvas area in x
    ``y_bounds``      Bounds of canvas area in y
    ``y_min_gr_zero`` smallest y greater zero (need in log plotting)
    ``canvas``        Reference to the TCanvas instance
    ``main_pad``      Reference to TPad instance
    ``second_pad``    Reference to TPad instance or None
    ``first_drawn``   TObject which is first drawn (for valid TAxis reference)
    ``legend``        Reference to TLegend object.
    ================= =========================================================
    """
    class TooManyStacksError(Exception): pass
    class NoInputError(Exception): pass

    x_bounds       = 0., 0.
    y_bounds       = 0., 0.
    y_min_gr_zero  = 0.
    canvas         = None
    main_pad       = None
    second_pad     = None
    first_drawn    = None
    legend         = None

    def __init__(self, wrps, **kws):
        if not isinstance(wrps, collections.Iterable):
            raise self.NoInputError('CanvasBuilder wants iterable of wrps!')
        super(CanvasBuilder, self).__init__()
        self.kws = kws

        # only one stack, which should be one first place
        wrps = sorted(
            wrps,
            key=lambda r: not isinstance(r, wrappers.StackWrapper)
        )
        if len(wrps) > 1 and isinstance(wrps[1], wrappers.StackWrapper):
            raise self.TooManyStacksError(
                'CanvasWrapper takes at most one StackWrapper'
            )

        # for stacks and overlays
        if len(wrps) > 1:
            if isinstance(wrps[0], wrappers.StackWrapper):
                if not hasattr(wrps[0], 'draw_option'):
                    wrps[0].draw_option = 'hist'
                for w in wrps[1:]:
                    if not hasattr(w, 'draw_option'):
                        if w.is_signal:
                            w.draw_option = 'hist'
                            w.histo.SetLineWidth(2)
                        elif not w.is_data:  # circles for pseudo-data
                            w.draw_option = 'E0'
                            w.draw_option_legend = 'p'
                            w.histo.SetMarkerStyle(4)

        # instanciate Renderers
        rnds = list(_renderize_iter(wrps))
        self.renderers = rnds

        # name, title in_file_path
        self.name = kws.get('name', rnds[0].name)
        self.title = kws.get('title', rnds[0].title)
        self.in_file_path = kws.get('in_file_path', rnds[0].in_file_path)
        self.canvas_wrp = None

    def __del__(self):
        """Remove the pads first."""
        if self.main_pad:
            self.main_pad.Delete()
        if self.second_pad:
            self.second_pad.Delete()

    def configure(self):
        pass

    def find_x_y_bounds(self):
        """Scan ROOT-objects for x and y bounds."""
        rnds = self.renderers
        x_min = min(r.x_min() for r in rnds)
        x_max = max(r.x_max() for r in rnds)
        self.x_bounds = x_min, x_max
        y_min = min(r.y_min() for r in rnds)
        y_max = max(r.y_max() for r in rnds)
        self.y_bounds = y_min, y_max
        self.y_min_gr_zero = min(r.y_min_gr_zero() for r in rnds)

    def make_empty_canvas(self):
        """Instanciate ``self.canvas`` ."""
        self.canvas = TCanvas(
            self.name + '_' + util.random_hex_str(),
            self.title,
            settings.canvas_size_x,
            settings.canvas_size_y,
        )
        self.canvas.name = self.name
        self.main_pad = self.canvas

    def draw_full_plot(self):
        """The renderers draw method is called."""
        for i, rnd in enumerate(self.renderers):
            if not i:
                self.first_drawn = rnd.obj
                self.first_drawn.SetTitle('')
                rnd.draw('')
            else:
                rnd.draw('same')

    def do_final_cosmetics(self):
        """Pimp the canvas!"""
        _, y_max = self.y_bounds
        self.first_drawn.GetXaxis().SetNoExponent()
        self.first_drawn.GetXaxis().SetLabelSize(0.052)
        if self.first_drawn.GetMinimum() > 0.:
            self.first_drawn.SetMinimum(y_max / 10000.)
        self.first_drawn.SetMaximum(y_max * 1.2)

    def run_procedure(self):
        """
        This method calls all other methods, which fill and build the canvas.
        """
        self.configure()
        self.find_x_y_bounds()
        self.make_empty_canvas()
        self.draw_full_plot()
        self.do_final_cosmetics()

    def _track_canvas_history(self):
        list_of_histories = []
        for rnd in self.renderers:
            list_of_histories.append(rnd.history)
        hstry = history.History('CanvasBuilder')
        hstry.add_args(list_of_histories)
        hstry.add_kws(self.kws)
        return hstry

    def _del_builder_refs(self):
        for k, obj in self.__dict__.items():
            if isinstance(obj, TObject):
                setattr(self, k, None)

    def build_canvas(self):
        """
        With this method, the building procedure is started.

        :return: ``CanvasWrapper`` instance.
        """
        if not self.canvas:
            self.run_procedure()
        canvas = self.canvas
        canvas.Modified()
        canvas.Update()
        kws = self.renderers[0].all_info()  # TODO only common info
        for attr in ('is_signal', 'is_data', 'is_pseudo_data'):
            if attr in kws:
                del kws[attr]
        kws.update(self.kws)
        kws.update({
            'main_pad'    : self.main_pad,
            'second_pad'  : self.second_pad,
            'legend'      : self.legend,
            'first_drawn' : self.first_drawn,
            'x_bounds'    : self.x_bounds,
            'y_bounds'    : self.y_bounds,
            'y_min_gr_0'  : self.y_min_gr_zero,
            'history'     : self._track_canvas_history(),
            '_renderers'  : self.renderers,
        })
        wrp = wrappers.CanvasWrapper(canvas, **kws)
        self._del_builder_refs()
        self.canvas_wrp = wrp
        return wrp


############################################# customization with decorators ###
import util
import operations as op
from ROOT import TLegend, TPad, TPaveText


class TitleBox(util.Decorator):
    """
    Draws title-box with TPaveText above canvas window.

    Instanciate with text argument:
    ``tb = TitleBox(text='My funny title')``.
    """
    def do_final_cosmetics(self):
        self.decoratee.do_final_cosmetics()

        titlebox = TPaveText(0.5, 0.90, 0.98, 1.0, 'brNDC')
        titlebox.AddText(self.dec_par.get('text', 'ENTER TEXT FOR TITLEBOX!'))
        titlebox.SetTextSize(0.042)
        titlebox.SetFillStyle(0)
        titlebox.SetBorderSize(0)
        titlebox.SetTextAlign(31)
        titlebox.SetMargin(0.0)
        titlebox.SetFillColor(0)
        self.canvas.cd()
        titlebox.Draw('SAME')
        self.main_pad.cd()
        self.titlebox = titlebox


class TextBox(util.Decorator):
    """
    Draw Textbox.

    Instanciate with textbox argument:
    ``tb = TextBox(textbox=ROOT.TLatex(0.5, 0.5, 'My Box'))``.
    """

    def do_final_cosmetics(self):
        if 'textbox' not in self.dec_par:
            self.dec_par['textbox'] = ROOT.TLatex(
                0.5, 0.5,
                'I need a textbox=ROOT.TLatex(0.5, 0.5, "My Box") parameter')
        self.decoratee.do_final_cosmetics()
        self.dec_par['textbox'].SetNDC()
        self.dec_par['textbox'].Draw()


class Legend(util.Decorator):
    """
    Adds a legend to the main_pad.

    Takes entries from ``self.main_pad.BuildLegend()`` .
    The box height is adjusted by the number of legend entries.
    No border or shadow are printed. See __init__ for keywords.

    You can set ``draw_option_legend`` on a wrapper. If it evaluates to
    ``False`` (like an empty string), the item will be removed from the legend.

    All default settings in ``settings.defaults_Legend`` can be overwritten by
    providing an argument with the same name, e.g. ``Legend(x_pos=0.2)``.
    """
    def __init__(self, inner=None, dd='True', **kws):
        super(Legend, self).__init__(inner, dd)
        self.dec_par.update(settings.defaults_Legend)
        self.dec_par.update(kws)

    def make_entry_tupels(self, legend):
        rnds = self.renderers
        entries = []
        for entry in legend.GetListOfPrimitives():
            obj = entry.GetObject()
            label = entry.GetLabel()
            draw_opt = self.dec_par['opt']
            for rnd in rnds:

                # match legend entries to renderers
                if getattr(rnd, 'graph_draw', rnd.obj) is not obj:
                    continue

                if isinstance(rnd, StackRenderer):
                    continue

                if rnd.is_data:
                    draw_opt = self.dec_par['opt_data']
                else:
                    draw_opt = 'l'

                if hasattr(rnd, 'legend'):
                    label = rnd.legend
                if hasattr(rnd, 'draw_option_legend'):
                    draw_opt = rnd.draw_option_legend
                break

            if draw_opt:  # empty string -> no legend entry
                entries.append((obj, label, draw_opt))
        return entries

    def _calc_bounds(self, n_entries):
        par = self.dec_par
        if 'xy_coords' in par:
            xy = par['xy_coords']
            assert len(xy) == 4 and all(type(z) == float for z in xy)
            return xy
        else:
            x_pos   = par['x_pos']
            y_pos   = par['y_pos']
            width   = par['label_width']
            height  = par['label_height'] * n_entries
            if y_pos + height/2. > 1.:
                 y_pos = 1 - height/2. # do not go outside canvas
            return x_pos - width/2., \
                   y_pos - height/2., \
                   x_pos + width/2., \
                   y_pos + height/2.

    def do_final_cosmetics(self):
        """
        Only ``do_final_cosmetics`` is overwritten here.

        If self.legend == None, this method will create a default legend and
        store it to self.legend
        """
        if self.legend:
            return

        # get legend entry objects
        tmp_leg = self.main_pad.BuildLegend(0.1, 0.6, 0.5, 0.8)
        entries = self.make_entry_tupels(tmp_leg)
        tmp_leg.Clear()
        self.main_pad.GetListOfPrimitives().Remove(tmp_leg)
        tmp_leg.Delete()

        # get legend entry objects from bottom plot
        if self.second_pad:
            tmp_leg_bot = self.second_pad.BuildLegend(0.1, 0.6, 0.5, 0.8)
            entries_bot = self.make_entry_tupels(tmp_leg_bot)
            tmp_leg_bot.Clear()
            self.second_pad.GetListOfPrimitives().Remove(tmp_leg_bot)
            tmp_leg_bot.Delete()

            # entries_bot = list(itertools.ifilter(self.dec_par['clean_legend'], entries_bot))
            entries_bot = list(itertools.ifilter(lambda w: w[1] not in list(g[1] for g in entries), entries_bot))

            entries += entries_bot

        entries = list(itertools.ifilter(self.dec_par['clean_legend'], entries))

        # create a new legend
        bounds = self._calc_bounds(len(entries))
        legend = TLegend(*bounds)
        legend.SetBorderSize(0)
        legend.SetTextSize(
            self.dec_par.get('text_size', settings.box_text_size))
        if 'text_font' in self.dec_par:
            legend.SetTextFont(self.dec_par['text_font'])
        par = self.dec_par
        if par['reverse']:
            entries.reverse()
        entries = list(sorted(entries, key=par['sort_legend']))
        entries = list(sorted(entries, key=lambda w: 'uncert' in w[1]))
        for obj, label, draw_opt in entries:
            legend.AddEntry(obj, label, draw_opt)
        self.canvas.cd()
        legend.Draw()
        self.main_pad.cd()
        self.legend = legend
        self.decoratee.do_final_cosmetics()         # Call next inner class!!


class BottomPlot(util.Decorator):
    """Base class for all plot business at the bottom of the canvas."""
    def __init__(self, inner=None, dd=True, **kws):
        super(BottomPlot, self).__init__(inner, dd, **kws)
        self.dec_par.update(settings.defaults_BottomPlot)
        self.dec_par.update(kws)
        self.dec_par['renderers_check_ok'] = False

    def check_renderers(self):
        """Overwrite and return bool!"""
        return False

    def define_bottom_hist(self):
        """Overwrite this method and give a histo-ref to self.bottom_hist!"""
        pass

    def configure(self):
        self.decoratee.configure()
        check_ok = self.check_renderers()
        self.dec_par['renderers_check_ok'] = check_ok

        if check_ok:
            self.define_bottom_hist()

    def make_empty_canvas(self):
        """Instanciate canvas with two pads."""
        # canvas
        self.decoratee.make_empty_canvas()
        if not self.dec_par['renderers_check_ok']:
            return
        name = self.name
        self.main_pad = TPad(
            'main_pad_' + name,
            'main_pad_' + name,
            0, 0.25, 1, 1
        )
        # main (upper) pad
        main_pad = self.main_pad
        main_pad.SetTopMargin(0.125)
        main_pad.SetBottomMargin(0.)
        #main_pad.SetRightMargin(0.04)
        #main_pad.SetLeftMargin(0.16)
        main_pad.Draw()
        # bottom pad
        self.canvas.cd()
        self.second_pad = TPad(
            'bottom_pad_' + name,
            'bottom_pad_' + name,
            0, 0, 1, 0.25
        )
        second_pad = self.second_pad
        second_pad.SetTopMargin(0.)
        second_pad.SetBottomMargin(0.375)
        #second_pad.SetRightMargin(0.04)
        #second_pad.SetLeftMargin(0.16)
        second_pad.SetRightMargin(main_pad.GetRightMargin())
        second_pad.SetLeftMargin(main_pad.GetLeftMargin())
        second_pad.SetGridy()
        second_pad.Draw()

    def draw_full_plot(self):
        """Make bottom plot, draw both."""
        # draw main histogram
        self.main_pad.cd()
        self.decoratee.draw_full_plot()
        if not self.dec_par['renderers_check_ok']:
            return
        first_drawn = self.first_drawn
        first_drawn.GetYaxis().CenterTitle(1)
        first_drawn.GetYaxis().SetTitleSize(0.055)
        first_drawn.GetYaxis().SetTitleOffset(1.3)
        first_drawn.GetYaxis().SetLabelSize(0.055)
        first_drawn.GetXaxis().SetNdivisions(505)
        # make bottom histo and draw it
        self.second_pad.cd()
        # bottom_obj = getattr(self, 'bottom_graph', self.bottom_hist)
        bottom_obj = self.bottom_hist

        settings.set_bottom_plot_general_style(bottom_obj)
        # bottom_obj.SetMarkerStyle(20)
        # bottom_obj.SetMarkerSize(.7)
        # if isinstance(bottom_obj, ROOT.TH1):
        #     bottom_obj.Draw(self.dec_par['draw_opt'])

        y_min, y_max = self.dec_par['y_min'], self.dec_par['y_max']
        if isinstance(bottom_obj, ROOT.TH1) and not self.dec_par['force_y_range']:
            n_bins = bottom_obj.GetNbinsX()
            if all(bottom_obj.GetBinContent(i+1) == -500. for i in xrange(n_bins)):
                mini = y_min
            else:
                mini = min(bottom_obj.GetBinContent(i+1)
                           - bottom_obj.GetBinError(i+1) for i in xrange(n_bins) if bottom_obj.GetBinContent(i+1) != -500.) - .1
            maxi = max(bottom_obj.GetBinContent(i+1)
                       + bottom_obj.GetBinError(i+1) for i in xrange(n_bins)) + .1
            if mini < y_min or maxi > y_max:
                y_min, y_max = max(y_min, mini), min(y_max, maxi)
                y_range = max(abs(y_min), abs(y_max))
                y_min, y_max = -y_range, y_range
        bottom_obj.GetYaxis().SetRangeUser(y_min, y_max)

        self.y_min_max = y_min, y_max

        # set focus on main_pad for further drawing
        self.main_pad.cd()


class BottomPlotRatio(BottomPlot):
    """Ratio of first and second histogram in canvas."""

    def check_renderers(self):
        if 'TH2' in self.renderers[0].type:
            return False

        data_hists = list(r
                          for r in self.renderers
                          if r.is_data or r.is_pseudo_data)

        if len(data_hists) > 1:
            print 'ERROR BottomPlots can only be created with exactly '\
                         'one data histogram. N(Data hists): %s' % len(data_hists)
            return False

        return bool(data_hists)

    def define_bottom_hist(self):
        rnds = self.renderers
        wrp = op.div([rnds[0]] + list(r
                                      for r in rnds
                                      if r.is_data or r.is_pseudo_data))
        for i in xrange(1, wrp.histo.GetNbins() + 1):
            cont = wrp.histo.GetBinContent(i)
            wrp.histo.SetBinContent(i, cont - 1.)
        wrp.histo.SetYTitle(self.dec_par['y_title'] or '#frac{Data}{Bkg}')
        self.bottom_hist = wrp.histo

    def draw_full_plot(self):
        super(BottomPlotRatio, self).draw_full_plot()
        if not self.dec_par['renderers_check_ok']:
            return
        self.second_pad.cd()
        bottom_hist = self.bottom_hist
        # settings.set_bottom_plot_ratio_style(bottom_hist)
        bottom_hist.Draw(self.dec_par.get('draw_opt_first', self.dec_par['draw_opt']))
        self.main_pad.cd()


class BottomPlotRatioSplitErr(BottomPlotRatio):
    """Same as BottomPlotRatio, but split MC and data uncertainties."""

    def define_bottom_hist(self):
        rnds = self.renderers
        mcee_rnd = rnds[0]
        data_rnd = next(r for r in rnds if r.is_data or r.is_pseudo_data)
        y_title = self.dec_par['y_title'] or (
            '#frac{Data-Bkg}{Bkg}' if data_rnd.is_data else '#frac{Sig-Bkg}{Bkg}')

        def mk_bkg_errors(histo, ref_histo):
            for i in xrange(histo.GetNbinsX() + 2):
                val = histo.GetBinContent(i)
                ref_val = ref_histo.GetBinContent(i)
                err = histo.GetBinError(i)
                histo.SetBinContent(i, (val-ref_val)/(ref_val or 1e20))
                histo.SetBinError(i, err/(ref_val or 1e20))
            return histo

        # underlying error bands
        if mcee_rnd.histo_sys_err:
            stt_histo = mcee_rnd.histo.Clone()
            mk_bkg_errors(stt_histo, stt_histo)
            stt_histo.SetYTitle(y_title)
            settings.stat_error_style(stt_histo)

            sys_histo = mcee_rnd.histo_sys_err.Clone()
            mk_bkg_errors(sys_histo, mcee_rnd.histo)
            sys_histo.SetYTitle(y_title)
            settings.sys_error_style(sys_histo)

            tot_histo = mcee_rnd.histo_tot_err.Clone()
            mk_bkg_errors(tot_histo, mcee_rnd.histo)
            tot_histo.SetYTitle(y_title)
            settings.tot_error_style_bot(tot_histo)

            self.bottom_hist_stt_err = stt_histo
            self.bottom_hist_sys_err = sys_histo
            self.bottom_hist_tot_err = tot_histo

        else:
            stt_histo = mcee_rnd.histo.Clone()
            mk_bkg_errors(stt_histo, stt_histo)
            stt_histo.SetYTitle(y_title)
            settings.stat_error_style(stt_histo)

            self.bottom_hist_stt_err = stt_histo
            self.bottom_hist_sys_err = None
            self.bottom_hist_tot_err = None

        # overlaying ratio histogram
        mc_histo_no_err = mcee_rnd.histo.Clone()
        data_hist = data_rnd.histo
        div_hist = data_hist.Clone()
        div_hist.Sumw2()
        for i in xrange(mc_histo_no_err.GetNbinsX()+2):
            mc_histo_no_err.SetBinError(i, 0.)
            # if div_hist.GetBinContent(i) < 0.:
            #     div_hist.SetBinError(i, 1.8)
        div_hist.Add(mc_histo_no_err, -1)
        div_hist.Divide(mc_histo_no_err)
        div_hist.SetYTitle(y_title)
        self.bottom_hist = div_hist

        # poissonean error bars
        if self.dec_par['poisson_errs']:
            if hasattr(data_rnd, 'bin_width'):
                for i in xrange(data_hist.GetNbinsX()+2):
                    bin_count = data_hist.GetBinContent(i)*data_hist.GetBinWidth(i)/data_rnd.bin_width
                    data_hist.SetBinContent(i, bin_count)
            data_hist.SetBinErrorOption(ROOT.TH1.kPoisson)
            data_hist.Sumw2(False)
            gtop = ROOT.TGraphAsymmErrors(data_hist)
            gtop_empty = ROOT.TGraphAsymmErrors(data_hist)
            gbot = ROOT.TGraphAsymmErrors(div_hist)
            gtop_empty.SetMarkerStyle(1)
            div_hist.SetMarkerStyle(1)
            for i in xrange(mc_histo_no_err.GetNbinsX(), 0, -1):
                mc_val = mc_histo_no_err.GetBinContent(i)
                dat_val = data_hist.GetBinContent(i)
                x_val = mc_histo_no_err.GetBinCenter(i)
                x_err = 0.
                div_hist.SetBinError(i, 0.)
                if hasattr(self, 'draw_x_errs'):
                    x_err = data_hist.GetBinWidth(i)/2.
                # if dat_val <= 0.:
                #     x_val = mc_histo_no_err.GetBinCenter(i)
                #     gtop.SetPoint(i -1, x_val, -1.)
                # if mc_val:
                scl_fct = 1.
                if hasattr(data_rnd, 'bin_width'):
                    scl_fct = data_hist.GetBinWidth(i)/data_rnd.bin_width
                    # bin_count = data_hist.GetBinContent(i)
                    # data_hist.SetBinContent(i, bin_count/scl_fct)

                if mc_val and dat_val > 0.:
                    e_up = data_hist.GetBinErrorUp(i)
                    e_lo = data_hist.GetBinErrorLow(i)
                    gtop.SetPoint(i - 1, x_val, dat_val/scl_fct)
                    gtop.SetPointError(i - 1, x_err, x_err, e_lo/scl_fct, e_up/scl_fct)
                    gbot.SetPointError(i - 1, x_err, x_err, e_lo/mc_val, e_up/mc_val)
                    gtop_empty.RemovePoint(i - 1)
                elif mc_val:
                    e_up = data_hist.GetBinErrorUp(i)
                    e_lo = data_hist.GetBinErrorLow(i)
                    gtop_empty.SetPointError(i - 1, x_err, x_err, e_lo/scl_fct, e_up/scl_fct)
                    gbot.SetPointError(i - 1, x_err, x_err, e_lo/mc_val, e_up/mc_val)
                    gtop.RemovePoint(i - 1)
                else:
                    gtop.RemovePoint(i - 1)
                    gtop_empty.RemovePoint(i - 1)
                    gbot.RemovePoint(i - 1)

            gtop.SetTitle('Data')
            gtop_empty.SetTitle('dummy')
            data_hist.Sumw2()
            data_rnd.graph_draw = gtop
            data_rnd.draw_option = '0P'
            self.dec_par['draw_opt'] = '0P'
            self.dec_par['draw_opt_first'] = '0P'
            gbot.GetYaxis().SetTitle(y_title)
            h_x_ax, g_x_ax = div_hist.GetXaxis(), gbot.GetXaxis()
            g_x_ax.SetTitle(h_x_ax.GetTitle())
            g_x_ax.SetRangeUser(h_x_ax.GetXmin(), h_x_ax.GetXmax())
            self.bottom_graph = gbot
            # self.bottom_hist = self.bottom_hist_tot_err if self.bottom_hist_tot_err else self.bottom_hist_stt_err
            self.graph_empty = gtop_empty

        # for empty MC set data out of the frame
        for i in xrange(mc_histo_no_err.GetNbinsX()+2):
            if not div_hist.GetBinContent(i) and not mc_histo_no_err.GetBinContent(i):
                # if not mc_histo_no_err.GetBinContent(i):
                div_hist.SetBinContent(i, -500)
                div_hist.SetBinError(i, 0)

    def fix_bkg_err_values(self, histo):
        # errors are not plottet, if the bin center is out of the y bounds.
        # this function fixes it.
        y_min, y_max = self.y_min_max
        for i in xrange(1, histo.GetNbinsX() + 1):
            val = histo.GetBinContent(i)
            new_val = 0
            if val <= y_min:
                new_val = y_min * 0.99
            elif val >= y_max:
                new_val = y_max * 0.99
            if new_val:
                new_err = histo.GetBinError(i) - abs(new_val - val)
                new_err = max(new_err, 0)  # may not be negative
                histo.SetBinContent(i, new_val)
                histo.SetBinError(i, new_err)
        settings.set_bottom_plot_general_style(histo)
        histo.GetYaxis().SetRangeUser(y_min, y_max)

    def draw_full_plot(self):
        """Draw mc error histo below data ratio."""
        super(BottomPlotRatioSplitErr, self).draw_full_plot()
        if not self.dec_par['renderers_check_ok']:
            return


        if hasattr(self, 'graph_empty'):
            self.graph_empty.Draw('same0P')

        self.second_pad.cd()
        if self.bottom_hist_tot_err:
            self.fix_bkg_err_values(self.bottom_hist_stt_err)
            self.fix_bkg_err_values(self.bottom_hist_tot_err)
            self.bottom_hist_tot_err.Draw('sameE2')
            self.bottom_hist_stt_err.Draw('sameE2')
        else:
            self.fix_bkg_err_values(self.bottom_hist_stt_err)
            self.bottom_hist_stt_err.Draw('sameE2')

        bottom_obj = getattr(self, 'bottom_graph', self.bottom_hist)
        bottom_obj.Draw('same' + self.dec_par['draw_opt'])
        self.main_pad.cd()


class BottomPlotRatioPullErr(BottomPlot):
    """Same as BottomPlotRatio, but split MC and data uncertainties."""
    def check_renderers(self):
        if 'TH2' in self.renderers[0].type:
            return False

        data_hists = list(r
                          for r in self.renderers
                          if r.is_data or r.is_pseudo_data)

        if len(data_hists) > 1:
            print 'ERROR BottomPlots can only be created with exactly '\
                         'one data histogram. Data hists: %s' % data_hists
            return False

        return bool(data_hists)

    def define_bottom_hist(self):
        rnds = self.renderers
        mcee_rnd = rnds[0]
        data_rnd = next(r for r in rnds if r.is_data or r.is_pseudo_data)
        y_title = self.dec_par['y_title'] or (
            '#frac{Data-Bkg}{#sigma}' if data_rnd.is_data else '#frac{Sig-Bkg}{Bkg}')

        # overlaying ratio histogram
        mc_histo = mcee_rnd.histo
        data_hist = data_rnd.histo                      # NO CLONE HERE!
        sigma_histo = mcee_rnd.histo.Clone()
        data_hist.SetBinErrorOption(ROOT.TH1.kPoisson)
        mc_histo.SetBinErrorOption(ROOT.TH1.kPoisson)
        for i in xrange(mc_histo.GetNbinsX()+2):
            sigma_histo.SetBinError(i, 0.)
            # pm stands for plusminus
            pm = 1. if data_hist.GetBinContent(i) > mc_histo.GetBinContent(i) else -1.
            mc_sig_stat = mc_histo.GetBinErrorUp(i) if pm > 0 else mc_histo.GetBinErrorLow(i)
            data_sig_stat = data_hist.GetBinErrorLow(i) if pm > 0 else data_hist.GetBinErrorUp(i)
            if not data_hist.GetBinContent(i):
                data_sig_stat = 1.8
            if not mc_histo.GetBinContent(i):
                mc_sig_stat = 1.8
            mc_sig_syst = 0.
            if mcee_rnd.histo_sys_err:
                mc_sys_hist = mcee_rnd.histo_sys_err
                mc_sig_syst = mc_sys_hist.GetBinError(i) + pm*abs(
                                        mc_histo.GetBinContent(i) - mc_sys_hist.GetBinContent(i))
            sqr_quad = sqrt(mc_sig_stat**2+data_sig_stat**2+mc_sig_syst**2) or 1e-10
            sigma_histo.SetBinContent(i, sqr_quad)

        div_hist = data_hist.Clone()                    # NOW CLONING!
        div_hist.Add(mc_histo, -1)
        div_hist.Divide(sigma_histo)
        div_hist.SetYTitle(y_title)
        self.bottom_hist = div_hist

    def draw_full_plot(self):
        """Draw mc error histo below data ratio."""
        super(BottomPlotRatioPullErr, self).draw_full_plot()
        if not self.dec_par['renderers_check_ok']:
            return
        self.second_pad.cd()
        bottom_hist = self.bottom_hist
        y_min, y_max = self.dec_par['y_min'], self.dec_par['y_max']
        if isinstance(bottom_hist, ROOT.TH1):
            n_bins = bottom_hist.GetNbinsX()
            mini = min(bottom_hist.GetBinContent(i+1)
                       - bottom_hist.GetBinError(i+1) for i in xrange(n_bins)) - .1
            maxi = max(bottom_hist.GetBinContent(i+1)
                       + bottom_hist.GetBinError(i+1) for i in xrange(n_bins)) + .1
            if mini < y_min or maxi > y_max:
                y_min, y_max = min(y_min, mini), max(y_max, maxi)
                bottom_hist.GetYaxis().SetRangeUser(y_min, y_max)
        settings.set_bottom_plot_pull_style(bottom_hist)
        bottom_hist.Draw('same hist')
        self.main_pad.cd()


default_decorators = [
    BottomPlotRatioSplitErr,
    Legend
]


# TODO use WrapperWrapper info on construction
# TODO make a setting for choosing the default bottom plot
# TODO BottomPlotSignificance
# TODO redesign all canvas-making. Abandon Decorators. Use generators.
