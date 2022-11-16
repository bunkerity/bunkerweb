import { getEventTarget } from "../utils/dom";
function momentPlugin(config) {
    var moment = config.moment;
    return function (fp) {
        function captureIncrement(e) {
            var event = e;
            event.stopPropagation();
            var date = moment(fp.selectedDates[0]);
            var input = getEventTarget(event);
            var unit = Array.from(input.classList)
                .filter(function (name) { return name.startsWith("flatpickr-"); })
                .map(function (name) { return name.substring(10); })[0];
            var step = parseFloat(input.getAttribute("step"));
            date.add(step * event.delta, unit);
            fp.setDate(date.toDate());
        }
        return {
            parseDate: function (datestr, format) {
                return moment(datestr, format, true).toDate();
            },
            formatDate: function (date, format) {
                var momentDate = moment(date);
                if (typeof fp.config.locale === "string") {
                    momentDate.locale(fp.config.locale);
                }
                return momentDate.format(format);
            },
            onReady: function () {
                [fp.hourElement, fp.minuteElement, fp.secondElement].forEach(function (element) {
                    return element &&
                        element.addEventListener("increment", captureIncrement, {
                            capture: true,
                        });
                });
            },
            onDestroy: function () {
                [fp.hourElement, fp.minuteElement, fp.secondElement].forEach(function (element) {
                    return element &&
                        element.removeEventListener("increment", captureIncrement, {
                            capture: true,
                        });
                });
            },
        };
    };
}
export default momentPlugin;
