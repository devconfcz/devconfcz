function scroll_to_section(section /* Pass element id with # */) {
  // Get position of scroll target from top
  scroll_to = $(section).offset().top - $("#page-top").offset().top - ( $(section + " h2").outerHeight() / 2 )
  $('html, body').animate({
    scrollTop: scroll_to
 }, 1000);
}

(function ($) {
  $(document).ready(function(){
    var travel_height = $('#travel-text')[0].scrollHeight;
    $('#more-text').click(function(e) {
        e.stopPropagation();
        $('#travel-text').animate({
            'height': travel_height
        }, 1500)
        $('#more-text').css('display', 'none')
        $('#less-text').css('display', 'inherit')
    });
    $('#less-text').click(function() {
        $('#travel-text').animate({
            'height': '400px'
        }, 1500)
        $('#more-text').css('display', 'inherit')
        $('#less-text').css('display', 'none')
    })

    // get distance from top of the bottom logo border
    logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top

    // user can load already scrolled page (eg. refreshing, ...); check it even on document ready
    if ($(this).scrollTop() > logo_pos) {
      $('.navbar-brand').fadeIn();
    } else {
      $('.navbar-brand').fadeOut();
    }

    // hook on scroll and show/hide navbar
    $(function () {
      $(window).scroll(function () {
        // Keep amount of things here at minimum to keep it smooth on low-end devices
        if ($(this).scrollTop() > logo_pos) {
          $('.navbar-brand').fadeIn();
        } else {
          $('.navbar-brand').fadeOut();
        }
      });


    });
    var parser = document.createElement('a');
    parser.href = document.URL;
    accepted_sections = ["#about", "#venue", "#contact"]
    if ($.inArray(parser.hash, accepted_sections) != -1) {
      scroll_to_section(parser.hash)
    }
});
  }(jQuery));
