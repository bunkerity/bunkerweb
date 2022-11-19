import {registerListeners, unregisterListeners} from './lib/event.js';
import {formatDate} from './lib/date-format.js';
import Datepicker from './Datepicker.js';

// filter out the config options inapproprite to pass to Datepicker
function filterOptions(options) {
  const newOpts = Object.assign({}, options);

  delete newOpts.inputs;
  delete newOpts.allowOneSidedRange;
  delete newOpts.maxNumberOfDates; // to ensure each datepicker handles a single date

  return newOpts;
}

function setupDatepicker(rangepicker, changeDateListener, el, options) {
  registerListeners(rangepicker, [
    [el, 'changeDate', changeDateListener],
  ]);
  new Datepicker(el, options, rangepicker);
}

function onChangeDate(rangepicker, ev) {
  // to prevent both datepickers trigger the other side's update each other
  if (rangepicker._updating) {
    return;
  }
  rangepicker._updating = true;

  const target = ev.target;
  if (target.datepicker === undefined) {
    return;
  }

  const datepickers = rangepicker.datepickers;
  const setDateOptions = {render: false};
  const changedSide = rangepicker.inputs.indexOf(target);
  const otherSide = changedSide === 0 ? 1 : 0;
  const changedDate = datepickers[changedSide].dates[0];
  const otherDate = datepickers[otherSide].dates[0];

  if (changedDate !== undefined && otherDate !== undefined) {
    // if the start of the range > the end, swap them
    if (changedSide === 0 && changedDate > otherDate) {
      datepickers[0].setDate(otherDate, setDateOptions);
      datepickers[1].setDate(changedDate, setDateOptions);
    } else if (changedSide === 1 && changedDate < otherDate) {
      datepickers[0].setDate(changedDate, setDateOptions);
      datepickers[1].setDate(otherDate, setDateOptions);
    }
  } else if (!rangepicker.allowOneSidedRange) {
    // to prevent the range from becoming one-sided, copy changed side's
    // selection (no matter if it's empty) to the other side
    if (changedDate !== undefined || otherDate !== undefined) {
      setDateOptions.clear = true;
      datepickers[otherSide].setDate(datepickers[changedSide].dates, setDateOptions);
    }
  }
  datepickers[0].picker.update().render();
  datepickers[1].picker.update().render();
  delete rangepicker._updating;
}

/**
 * Class representing a date range picker
 */
export default class DateRangePicker  {
  /**
   * Create a date range picker
   * @param  {Element} element - element to bind a date range picker
   * @param  {Object} [options] - config options
   */
  constructor(element, options = {}) {
    const inputs = Array.isArray(options.inputs)
      ? options.inputs
      : Array.from(element.querySelectorAll('input'));
    if (inputs.length < 2) {
      return;
    }

    element.rangepicker = this;
    this.element = element;
    this.inputs = inputs.slice(0, 2);
    this.allowOneSidedRange = !!options.allowOneSidedRange;

    const changeDateListener = onChangeDate.bind(null, this);
    const cleanOptions = filterOptions(options);
    // in order for initial date setup to work right when pcicLvel > 0,
    // let Datepicker constructor add the instance to the rangepicker
    const datepickers = [];
    Object.defineProperty(this, 'datepickers', {
      get() {
        return datepickers;
      },
    });
    setupDatepicker(this, changeDateListener, this.inputs[0], cleanOptions);
    setupDatepicker(this, changeDateListener, this.inputs[1], cleanOptions);
    Object.freeze(datepickers);
    // normalize the range if inital dates are given
    if (datepickers[0].dates.length > 0) {
      onChangeDate(this, {target: this.inputs[0]});
    } else if (datepickers[1].dates.length > 0) {
      onChangeDate(this, {target: this.inputs[1]});
    }
  }

  /**
   * @type {Array} - selected date of the linked date pickers
   */
  get dates() {
    return this.datepickers.length === 2
      ? [
          this.datepickers[0].dates[0],
          this.datepickers[1].dates[0],
        ]
      : undefined;
  }

  /**
   * Set new values to the config options
   * @param {Object} options - config options to update
   */
  setOptions(options) {
    this.allowOneSidedRange = !!options.allowOneSidedRange;

    const cleanOptions = filterOptions(options);
    this.datepickers[0].setOptions(cleanOptions);
    this.datepickers[1].setOptions(cleanOptions);
  }

  /**
   * Destroy the DateRangePicker instance
   * @return {DateRangePicker} - the instance destroyed
   */
  destroy() {
    this.datepickers[0].destroy();
    this.datepickers[1].destroy();
    unregisterListeners(this);
    delete this.element.rangepicker;
  }

  /**
   * Get the start and end dates of the date range
   *
   * The method returns Date objects by default. If format string is passed,
   * it returns date strings formatted in given format.
   * The result array always contains 2 items (start date/end date) and
   * undefined is used for unselected side. (e.g. If none is selected,
   * the result will be [undefined, undefined]. If only the end date is set
   * when allowOneSidedRange config option is true, [undefined, endDate] will
   * be returned.)
   *
   * @param  {String} [format] - Format string to stringify the dates
   * @return {Array} - Start and end dates
   */
  getDates(format = undefined) {
    const callback = format
      ? date => formatDate(date, format, this.datepickers[0].config.locale)
      : date => new Date(date);

    return this.dates.map(date => date === undefined ? date : callback(date));
  }

  /**
   * Set the start and end dates of the date range
   *
   * The method calls datepicker.setDate() internally using each of the
   * arguments in start→end order.
   *
   * When a clear: true option object is passed instead of a date, the method
   * clears the date.
   *
   * If an invalid date, the same date as the current one or an option object
   * without clear: true is passed, the method considers that argument as an
   * "ineffective" argument because calling datepicker.setDate() with those
   * values makes no changes to the date selection.
   *
   * When the allowOneSidedRange config option is false, passing {clear: true}
   * to clear the range works only when it is done to the last effective
   * argument (in other words, passed to rangeEnd or to rangeStart along with
   * ineffective rangeEnd). This is because when the date range is changed,
   * it gets normalized based on the last change at the end of the changing
   * process.
   *
   * @param {Date|Number|String|Object} rangeStart - Start date of the range
   * or {clear: true} to clear the date
   * @param {Date|Number|String|Object} rangeEnd - End date of the range
   * or {clear: true} to clear the date
   */
  setDates(rangeStart, rangeEnd) {
    const [datepicker0, datepicker1] = this.datepickers;
    const origDates = this.dates;

    // If range normalization runs on every change, we can't set a new range
    // that starts after the end of the current range correctly because the
    // normalization process swaps start↔︎end right after setting the new start
    // date. To prevent this, the normalization process needs to run once after
    // both of the new dates are set.
    this._updating = true;
    datepicker0.setDate(rangeStart);
    datepicker1.setDate(rangeEnd);
    delete this._updating;

    if (datepicker1.dates[0] !== origDates[1]) {
      onChangeDate(this, {target: this.inputs[1]});
    } else if (datepicker0.dates[0] !== origDates[0]) {
      onChangeDate(this, {target: this.inputs[0]});
    }
  }
}
