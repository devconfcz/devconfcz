(function ($) {
  $(document).ready(function(){

  // hide .navbar first
  $(".navbar").hide();

  // get logo distance from top
  logo_pos = $("#devconf-logo").offset().top - $("#page-top").offset().top

  // user can load already scrolled page (eg. refreshing, ...); check it even on document ready
  if ($(this).scrollTop() > logo_pos) {
    $('.navbar').fadeIn();
  } else {
    $('.navbar').fadeOut();
  }

  // hook on scroll and show/hide navbar
  $(function () {
    $(window).scroll(function () {
      // set distance user needs to scroll before we fadeIn navbar
      // FIXME: Make this START at the ABOUT page
      if ($(this).scrollTop() > logo_pos) {
        $('.navbar').fadeIn();
      } else {
        $('.navbar').fadeOut();
      }
    });


  });

});
  }(jQuery));
